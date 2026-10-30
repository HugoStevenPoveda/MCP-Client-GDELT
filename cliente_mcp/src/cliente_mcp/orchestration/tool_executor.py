"""
Tool Executor: Ejecuta tools con validación y dispatch a handlers.
Desacoplado del LLM y del cliente MCP.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger
import json

from cliente_mcp.core.models import ToolType
from cliente_mcp.validators.workflow_validator import WorkflowValidator
from cliente_mcp.validators.tool_classifier import ToolClassifier
from cliente_mcp.handlers.construction_handler import ConstructionHandler
from cliente_mcp.handlers.preconsulta_handler import PreconsultaHandler
from cliente_mcp.handlers.query_handler import QueryHandler
from cliente_mcp.handlers.synthesis_handler import SynthesisHandler


class ToolExecutor:
    """
    Ejecuta tools con validación de workflow y dispatch a handlers.

    Responsabilidades:
    - Validar que las tools pueden ejecutarse según el workflow
    - Dispatch a handler correcto según tipo de tool
    - Retornar resultados en formato estándar
    """

    def __init__(
        self,
        validator: WorkflowValidator,
        classifier: ToolClassifier,
        construction_handler: ConstructionHandler,
        preconsulta_handler: PreconsultaHandler,
        query_handler: QueryHandler,
        synthesis_handler: SynthesisHandler,
        tool_to_client_map: Dict[str, Any],
        graphrag_agent: Optional[Any] = None,
    ):
        """
        Inicializa el executor.

        Args:
            validator: Validador de workflow
            classifier: Clasificador de tools
            construction_handler: Handler para construcción
            preconsulta_handler: Handler para preconsulta
            query_handler: Handler para queries
            synthesis_handler: Handler para síntesis
            tool_to_client_map: Mapeo de tool_name -> MCP client
        """
        self.validator = validator
        self.classifier = classifier
        self.construction_handler = construction_handler
        self.preconsulta_handler = preconsulta_handler
        self.query_handler = query_handler
        self.synthesis_handler = synthesis_handler
        self.tool_to_client  = tool_to_client_map
        self.graphrag_agent  = graphrag_agent

    async def execute_tools(self, tool_calls: List, log) -> List[Dict]:
        """
        Ejecuta lista de tool calls con validación.

        Args:
            tool_calls: Lista de ToolCall objects del LLM
            log: Logger con contexto

        Returns:
            Lista de resultados en formato:
            [{"type": "tool_result", "tool_use_id": "...", "content": "..."}]
        """
        tool_results = []

        for tool_call in tool_calls:
            tool_name = tool_call.name
            tool_id = tool_call.id
            params = tool_call.input

            log.info(f"🛠️  Tool solicitado: {tool_name}")
            log.debug(f"   Argumentos: {json.dumps(params, ensure_ascii=False)}")

            # ==================== VALIDACIÓN ESPECIAL PARA SYNTHESIS ====================
            if tool_name == "synthesize_final_response":
                synthesis_validation = self.validator.validate_synthesis_ready()

                if not synthesis_validation.valid:
                    log.warning(f"❌ Validación Fase 2 fallida: {synthesis_validation.error_message}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": json.dumps({
                            "status": "error",
                            "message": synthesis_validation.error_message,
                            "missing_queries": synthesis_validation.missing_tools,
                            "phase": "query_phase_incomplete"
                        }, ensure_ascii=False)
                    })
                    continue

            # ==================== VALIDACIÓN GENERAL ====================
            validation = self.validator.validate_execution(tool_name)

            if not validation.valid:
                log.warning(f"❌ Validación fallida: {validation.error_message}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": json.dumps({
                        "status": "error",
                        "message": validation.error_message,
                        "missing_tools": validation.missing_tools
                    }, ensure_ascii=False)
                })
                continue

            # ==================== DISPATCH POR TIPO ====================
            try:
                tool_type = self.classifier.get_tool_type(tool_name)
                result = await self._dispatch_tool_execution(tool_name, params, tool_type, log)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": result
                })

            except Exception as e:
                log.error(f"❌ ERROR ejecutando tool '{tool_name}': {e}")
                log.exception("Traceback completo:")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": json.dumps({
                        "status": "error",
                        "message": str(e)
                    })
                })

        return tool_results

    async def _dispatch_tool_execution(
        self,
        tool_name: str,
        params: Dict,
        tool_type: ToolType,
        log
    ) -> str:
        """
        Dispatch tool execution a handler correcto según tipo.

        Args:
            tool_name: Nombre de la tool
            params: Parámetros de la tool
            tool_type: ToolType enum
            log: Logger con contexto

        Returns:
            Resultado de la tool (formato JSON string)
        """
        if tool_type == ToolType.CONSTRUCTION:
            log.info(f"   🔨 Dispatching a ConstructionHandler")
            mcp_client = self._get_mcp_client(tool_name)
            return await self.construction_handler.execute(tool_name, params, mcp_client)

        elif tool_type == ToolType.PRECONSULTA:
            log.info(f"   🔍 Dispatching a PreconsultaHandler")
            mcp_client = self._get_mcp_client(tool_name)
            return await self.preconsulta_handler.execute(tool_name, params, mcp_client)

        elif tool_type == ToolType.QUERY:
            log.info(f"   🔍 Dispatching a QueryHandler")
            mcp_client = self._get_mcp_client(tool_name)
            return await self.query_handler.execute(tool_name, params, mcp_client)

        elif tool_type == ToolType.SYNTHETIC:
            if self.graphrag_agent:
                query = self.synthesis_handler.store.metadata.user_question or ""
                log.info("=" * 60)
                log.info("🚀 AGENTE 2 — GraphRAG SDK Loop iniciando")
                log.info(f"   Query: {query[:80]}")
                log.info("=" * 60)
                raw   = await self.graphrag_agent.run(query)
                # Guardar en logs/agente.json usando la misma funcion del modulo
                from agentGraphRag.agente_sdk import save_result
                save_result(raw)
                return json.dumps(raw, ensure_ascii=False)
            log.info("   🎯 Dispatching a SynthesisHandler (fallback)")
            return self.synthesis_handler.execute(params)

        else:
            raise ValueError(f"Unknown tool type: {tool_type}")

    def _get_mcp_client(self, tool_name: str):
        """
        Obtiene el MCP client correcto para una tool.

        Args:
            tool_name: Nombre de la tool

        Returns:
            MCP client instance
        """
        client = self.tool_to_client.get(tool_name)
        if not client:
            raise ValueError(f"Tool '{tool_name}' no encontrada en mapeo de clientes")
        return client
