"""
Implementación de LLMProvider para Anthropic/Claude.
"""

from anthropic import Anthropic
from typing import List, Dict, Any
from .base import LLMProvider, LLMResponse, ToolCall
from loguru import logger
import json


class AnthropicProvider(LLMProvider):
    """
    Implementación de LLMProvider para Anthropic/Claude.

    Encapsula toda la lógica específica de la API de Anthropic,
    permitiendo que el resto del sistema sea agnóstico del LLM.
    """

    def __init__(self, api_key: str, model: str = "claude-3-5-haiku-20241022"):
        """
        Inicializa el provider de Anthropic.

        Args:
            api_key: API key de Anthropic
            model: Modelo de Claude a usar
        """
        self.client = Anthropic(api_key=api_key)
        self.model = model
        logger.info(f"✓ AnthropicProvider inicializado | Modelo: {model}")

    async def chat(
        self,
        messages: List[Dict],
        system_prompt: str,
        tools: List[Dict],
        max_tokens: int,
        temperature: float
    ) -> LLMResponse:
        """
        Ejecuta chat con Anthropic API.

        Args:
            messages: Lista de mensajes en formato Anthropic
            system_prompt: System prompt
            tools: Tools en formato Anthropic
            max_tokens: Máximo de tokens
            temperature: Temperatura

        Returns:
            LLMResponse normalizado
        """
        logger.debug(f"📤 Llamando a Anthropic API | Model: {self.model}")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            tools=tools,
            temperature=temperature,
            system=system_prompt,
            messages=messages
        )

        logger.debug(f"📥 Respuesta recibida | Stop reason: {response.stop_reason}")

        # Extraer tool calls y contenido de texto
        tool_calls = []
        text_content = ""

        for block in response.content:
            if block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    input=block.input
                ))
            elif hasattr(block, "text"):
                text_content += block.text

        # Normalizar stop_reason
        stop_reason = self._normalize_stop_reason(response.stop_reason)

        return LLMResponse(
            content=text_content,
            stop_reason=stop_reason,
            raw_content=response.content,
            tool_calls=tool_calls
        )

    def format_tools(self, mcp_tools: List) -> List[Dict]:
        """
        Convierte tools MCP a formato Claude.

        Args:
            mcp_tools: Tools en formato MCP

        Returns:
            Tools en formato Claude
        """
        claude_tools = []

        for tool in mcp_tools:
            claude_tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            })

        logger.debug(f"🔧 Formateadas {len(claude_tools)} tools para Claude")
        return claude_tools

    def create_tool_result_message(self, tool_results: List[Dict]) -> Dict:
        """
        Crea mensaje con resultados de tools en formato Anthropic.

        Args:
            tool_results: Lista de resultados con formato:
                [{"type": "tool_result", "tool_use_id": "...", "content": "..."}]

        Returns:
            Mensaje en formato Anthropic
        """
        return {
            "role": "user",
            "content": tool_results
        }

    def serialize_assistant_message(self, raw_content: Any) -> Dict:
        """
        Serializa mensaje del asistente de Anthropic.

        Args:
            raw_content: Contenido raw de response.content

        Returns:
            Mensaje serializado para historial
        """
        content_serializable = []

        for block in raw_content:
            if hasattr(block, "model_dump"):
                content_serializable.append(block.model_dump())
            else:
                content_serializable.append({
                    "type": block.type,
                    "text": block.text if hasattr(block, "text") else str(block)
                })

        return {
            "role": "assistant",
            "content": content_serializable
        }

    def _normalize_stop_reason(self, anthropic_reason: str) -> str:
        """
        Normaliza stop_reason de Anthropic a formato común.

        Args:
            anthropic_reason: Stop reason de Anthropic

        Returns:
            Stop reason normalizado
        """
        mapping = {
            "tool_use": "tool_use",
            "end_turn": "complete",
            "max_tokens": "max_tokens",
            "stop_sequence": "stop"
        }
        return mapping.get(anthropic_reason, anthropic_reason)
