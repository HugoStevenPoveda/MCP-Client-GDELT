"""
Preconsulta handler for executing and tracking preconsulta phase tools.
Manages the 4-tool preconsulta workflow that runs after construction.
"""

import json
from typing import Any
from loguru import logger

from cliente_mcp.core.storage import ConversationStore
from cliente_mcp.validators.tool_classifier import ToolClassifier


def parse_mcp_result(result) -> dict:
    """
    Parse MCP CallToolResult to extract clean JSON data.

    Args:
        result: CallToolResult object from MCP client

    Returns:
        Parsed JSON as dict
    """
    try:
        # If result has content attribute (CallToolResult)
        if hasattr(result, 'content') and len(result.content) > 0:
            first_content = result.content[0]

            # Extract text from TextContent
            if hasattr(first_content, 'text'):
                json_text = first_content.text
                # Parse the JSON string to dict
                return json.loads(json_text)

        # Fallback: try to parse string representation
        result_str = str(result)
        if '{' in result_str:
            # Try to extract JSON from string
            start = result_str.find('{')
            end = result_str.rfind('}') + 1
            if start != -1 and end > start:
                json_str = result_str[start:end]
                return json.loads(json_str)

        # Last resort: return as dict with raw field
        return {"raw": str(result)}

    except Exception as e:
        logger.warning(f"Error parsing MCP result: {e}")
        return {"raw": str(result)}


class PreconsultaHandler:
    """
    Handles execution of preconsulta tools.
    Tracks progress through the preconsulta phase (get_tipos_relaciones,
    get_record_ids_recientes, query_by_gkg_record_id, query_gdelt_data).
    """

    def __init__(self, store: ConversationStore, classifier: ToolClassifier):
        """
        Initialize the preconsulta handler.

        Args:
            store: ConversationStore for tracking preconsulta status
            classifier: ToolClassifier for getting tool information
        """
        self.store = store
        self.classifier = classifier

    async def execute(
        self,
        tool_name: str,
        params: dict,
        mcp_client
    ) -> Any:
        """
        Execute a preconsulta tool and track its completion.

        Args:
            tool_name: Name of the preconsulta tool
            params: Parameters for the tool
            mcp_client: MCP client to execute the tool

        Returns:
            Result from the tool execution (passed through unchanged)
        """
        logger.info(f"🔍 Executing preconsulta tool: {tool_name}")

        # Special handling for query_by_gkg_record_id - execute batch
        if tool_name == "query_by_gkg_record_id":
            return await self._execute_query_by_gkg_record_id_batch(mcp_client)

        # Validate parameters for query_gdelt_data
        if tool_name == "query_gdelt_data":
            if not params or "sql_query" not in params:
                error_msg = (
                    "❌ Error: 'query_gdelt_data' requiere el parámetro 'sql_query'. "
                    "Debes proporcionar una consulta SQL válida. "
                    "Ejemplo: {\"sql_query\": \"SELECT COUNT(*) FROM gdelt_commercial_news WHERE date >= '2024-01-01'\"}"
                )
                logger.warning(f"⚠️  {error_msg}")
                return error_msg

        # Execute the tool via MCP client
        try:
            async with mcp_client:
                result = await mcp_client.call_tool(tool_name, params)

            # Parse result to clean JSON
            result_data = parse_mcp_result(result)

            logger.info(f"✓ Preconsulta tool executed: {tool_name}")
            logger.debug(f"   Result: {json.dumps(result_data, ensure_ascii=False)[:200]}...")

            # Mark as complete in storage (only in preconsulta, NOT in queries)
            self.store.mark_preconsulta_complete(tool_name, result_data)

            # Log progress
            progress = self.get_progress_message()
            logger.info(f"📊 Preconsulta progress: {progress}")

            # Save to JSON file (don't send full data to LLM)
            self.store.export_preconsulta_to_json()

            # Check if preconsulta is fully complete
            if self.store.is_preconsulta_complete():
                logger.info("✅ FASE PRECONSULTA COMPLETE - All 4 tools done! Ready for FASE DE CONSULTAS")

            # Return brief summary instead of full data
            summary = self._create_brief_summary(tool_name, result_data)
            return summary

        except Exception as e:
            logger.error(f"❌ Error executing preconsulta tool '{tool_name}': {e}")
            raise

    async def _execute_query_by_gkg_record_id_batch(self, mcp_client) -> str:
        """
        Execute query_by_gkg_record_id for multiple record IDs automatically.
        Extracts record IDs from get_record_ids_recientes and queries each one.

        Args:
            mcp_client: MCP client to execute the tool

        Returns:
            Brief summary message about tripletas extracted
        """
        logger.info("🎯 Executing batch query_by_gkg_record_id for multiple documents")

        # Get record_ids from preconsulta data
        preconsulta_status = self.store.get_preconsulta_status()
        record_ids_status = preconsulta_status.get("get_record_ids_recientes")

        if not record_ids_status or not record_ids_status.completed:
            error_msg = "❌ Error: get_record_ids_recientes debe ejecutarse antes de query_by_gkg_record_id"
            logger.warning(error_msg)
            return error_msg

        # Extract record_ids from result
        record_ids_data = record_ids_status.result
        record_ids = []

        if isinstance(record_ids_data, dict):
            # Could be {"record_ids": "123,456,789"} or {"record_ids": [123, 456]}
            ids_value = record_ids_data.get("record_ids", "")
            if isinstance(ids_value, str):
                # Parse comma-separated string
                record_ids = [rid.strip() for rid in ids_value.split(",") if rid.strip()]
            elif isinstance(ids_value, list):
                record_ids = [str(rid) for rid in ids_value]

        if not record_ids:
            error_msg = "❌ Error: No se encontraron record_ids en get_record_ids_recientes"
            logger.warning(error_msg)
            return error_msg

        # Limit to first 10 IDs
        max_ids = 10
        record_ids = record_ids[:max_ids]
        logger.info(f"📊 Processing {len(record_ids)} record IDs (limited to {max_ids})")

        # Accumulate all tripletas
        all_tripletas = []
        documents_processed = 0

        try:
            async with mcp_client:
                for idx, record_id in enumerate(record_ids, 1):
                    logger.info(f"   [{idx}/{len(record_ids)}] Querying record_id: {record_id}")

                    try:
                        # Execute query for this record_id
                        result = await mcp_client.call_tool(
                            "query_by_gkg_record_id",
                            {"gkg_record_id": record_id}
                        )

                        # Parse result
                        result_data = parse_mcp_result(result)

                        # Extract tripletas from results array
                        if "results" in result_data:
                            tripletas = result_data["results"]
                            logger.info(f"      ✓ Found {len(tripletas)} tripletas in document {record_id}")

                            # Add record_id to each tripleta for reference
                            for tripleta in tripletas:
                                if isinstance(tripleta, dict):
                                    tripleta["source_record_id"] = record_id
                                    all_tripletas.append(tripleta)

                            documents_processed += 1

                    except Exception as e:
                        logger.warning(f"      ⚠️  Error querying record_id {record_id}: {e}")
                        continue

            # Store accumulated data
            batch_result = {
                "tripletas": all_tripletas,
                "total_tripletas": len(all_tripletas),
                "documentos_procesados": documents_processed,
                "record_ids_procesados": record_ids[:documents_processed]
            }

            logger.info(f"✅ Batch complete: {len(all_tripletas)} tripletas from {documents_processed} documents")

            # Mark as complete in storage
            self.store.mark_preconsulta_complete("query_by_gkg_record_id", batch_result)

            # Save to JSON
            self.store.export_preconsulta_to_json()

            # Log progress
            progress = self.get_progress_message()
            logger.info(f"📊 Preconsulta progress: {progress}")

            # Check if complete
            if self.store.is_preconsulta_complete():
                logger.info("✅ FASE PRECONSULTA COMPLETE - All 4 tools done! Ready for FASE DE CONSULTAS")

            # Return brief summary
            return f"✅ Preconsulta completada: query_by_gkg_record_id ({len(all_tripletas)} tripletas extraídas de {documents_processed} documentos)"

        except Exception as e:
            logger.error(f"❌ Error in batch query_by_gkg_record_id: {e}")
            raise

    def _create_brief_summary(self, tool_name: str, result_data: dict) -> str:
        """
        Create a brief summary of preconsulta results to send to LLM.

        Args:
            tool_name: Name of the tool executed
            result_data: Parsed result data as dict

        Returns:
            Brief summary message
        """
        try:
            # get_tipos_relaciones
            if "relaciones" in result_data:
                relations = result_data.get("relaciones", "")
                count = len(relations.split(", ")) if relations else 0
                return f"✅ Preconsulta completada: {tool_name} ({count} tipos de relaciones encontradas)"

            # get_record_ids_recientes
            elif "record_ids" in result_data:
                ids_str = result_data.get("record_ids", "")
                # Could be string or list
                if isinstance(ids_str, str):
                    count = len(ids_str.split(","))
                else:
                    count = len(ids_str)
                return f"✅ Preconsulta completada: {tool_name} ({count} record IDs recientes encontrados)"

            # query_gdelt_data
            elif "data" in result_data or "eventos" in result_data:
                eventos = result_data.get("eventos", result_data.get("data", []))
                count = len(eventos) if isinstance(eventos, list) else 0
                return f"✅ Preconsulta completada: {tool_name} ({count} registros encontrados)"

            else:
                # Generic fallback
                return f"✅ Preconsulta completada: {tool_name} (datos guardados exitosamente)"

        except Exception as e:
            logger.debug(f"Error creating brief summary: {e}")
            return f"✅ Preconsulta completada: {tool_name} (datos guardados exitosamente)"

    def get_progress_message(self) -> str:
        """
        Get a progress message for preconsulta phase.

        Returns:
            Progress string like "3/4 completed"
        """
        status = self.store.get_preconsulta_status()
        completed_count = len([s for s in status.values() if s.completed])
        total_required = 4
        return f"{completed_count}/{total_required} completed"

    def get_missing_tools(self) -> list:
        """
        Get list of missing preconsulta tools.

        Returns:
            List of tool names that are not yet completed
        """
        return self.store.get_missing_preconsulta_tools()

    def is_complete(self) -> bool:
        """
        Check if preconsulta phase is complete.

        Returns:
            True if all 4 preconsulta tools are done
        """
        return self.store.is_preconsulta_complete()

    def __repr__(self) -> str:
        progress = self.get_progress_message()
        return f"PreconsultaHandler(progress={progress}, complete={self.is_complete()})"
