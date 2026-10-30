"""
Query handler for executing and caching query results.
Intercepts real results and returns simplified confirmations to Claude.
"""

import json
from typing import Any
from loguru import logger

from cliente_mcp.core.storage import ConversationStore


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


class QueryHandler:
    """
    Handles execution of query tools.
    Caches real results but returns simplified confirmations.
    """

    def __init__(self, store: ConversationStore):
        """
        Initialize the query handler.

        Args:
            store: ConversationStore for caching query results
        """
        self.store = store

    async def execute(
        self,
        tool_name: str,
        params: dict,
        mcp_client
    ) -> str:
        """
        Execute a query tool, cache the result, and return a confirmation.

        Args:
            tool_name: Name of the query tool
            params: Parameters for the tool
            mcp_client: MCP client to execute the tool

        Returns:
            Simplified confirmation response (NOT the actual result)
        """
        logger.info(f"🔍 Executing query tool: {tool_name}")
        logger.debug(f"   Parameters: {json.dumps(params, ensure_ascii=False)}")

        # Register attempt BEFORE execution (counts even if fails)
        self.store.record_query_attempt(tool_name)
        logger.debug(f"   📊 Total attempts for '{tool_name}': {self.store.get_attempt_count(tool_name)}")

        # Execute the tool via MCP client
        try:
            async with mcp_client:
                result = await mcp_client.call_tool(tool_name, params)

            # Parse result to clean JSON format
            result_data = parse_mcp_result(result)

            logger.info(f"✓ Query executed successfully: {tool_name}")
            logger.debug(f"   Result preview: {json.dumps(result_data, ensure_ascii=False)[:200]}...")

            # Cache the REAL result (as parsed JSON)
            self.store.add_query_result(tool_name, params, result_data)

            # Save to queries.json immediately (incremental save)
            self.store.export_queries_to_json()
            logger.debug("   💾 Queries saved to logs/queries.json")

            # Build simplified confirmation response
            confirmation = self.build_confirmation_response(tool_name)

            logger.info(f"📦 Query cached. Total queries: {self.store.get_query_count()}")

            return confirmation

        except Exception as e:
            logger.error(f"❌ Error executing query tool '{tool_name}': {e}")
            # Return error to LLM - let it decide whether to retry with different params
            return json.dumps({
                "status": "error",
                "message": f"Query '{tool_name}' failed: {str(e)}",
                "note": "El intento ha sido registrado. Puedes reintentar con diferentes parámetros o continuar con otras consultas."
            }, ensure_ascii=False)

    def build_confirmation_response(self, tool_name: str) -> str:
        """
        Build a confirmation response for a query execution.

        Args:
            tool_name: Name of the executed tool

        Returns:
            JSON string with confirmation message
        """
        query_count = self.store.get_query_count()

        response = {
            "status": "query_executed",
            "tool": tool_name,
            "queries_count": query_count,
            "message": (
                f"✓ Consulta '{tool_name}' ejecutada exitosamente. "
                f"Tienes {query_count} consulta(s) acumulada(s). "
                f"Cuando tengas suficiente información (2-4 consultas típicamente), "
                f"llama a 'synthesize_final_response' para recibir todos los datos."
            )
        }

        return json.dumps(response, indent=2, ensure_ascii=False)

    def get_cached_queries_summary(self) -> dict:
        """
        Get a summary of all cached queries.

        Returns:
            Dictionary with cached query information
        """
        queries = self.store.get_all_queries()

        return {
            "total_count": len(queries),
            "queries": [
                {
                    "tool": q.tool_name,
                    "timestamp": q.timestamp.isoformat(),
                    "params": q.params,
                    "result_length": len(str(q.result))
                }
                for q in queries
            ]
        }

    def __repr__(self) -> str:
        query_count = self.store.get_query_count()
        return f"QueryHandler(cached_queries={query_count})"
