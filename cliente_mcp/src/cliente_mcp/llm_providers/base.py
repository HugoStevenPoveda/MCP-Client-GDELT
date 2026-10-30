"""
Interfaz base para proveedores de LLM.
Permite desacoplar la lógica de negocio del LLM específico.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class LLMMessage:
    """Mensaje normalizado para cualquier LLM."""
    role: str  # "user", "assistant", "system"
    content: Any  # Puede ser str, dict, list dependiendo del contexto


@dataclass
class ToolCall:
    """Llamada a tool normalizada."""
    id: str
    name: str
    input: Dict[str, Any]


@dataclass
class LLMResponse:
    """Respuesta normalizada de cualquier LLM."""
    content: str
    stop_reason: str  # "tool_use", "complete", "max_tokens", etc.
    raw_content: Any  # Contenido original del LLM para debugging
    tool_calls: List[ToolCall] = field(default_factory=list)


class LLMProvider(ABC):
    """
    Interfaz abstracta para proveedores de LLM.

    Cualquier LLM (Anthropic, OpenAI, etc.) debe implementar esta interfaz
    para ser compatible con el sistema de orquestación.
    """

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict],
        system_prompt: str,
        tools: List[Dict],
        max_tokens: int,
        temperature: float
    ) -> LLMResponse:
        """
        Ejecuta chat con el LLM.

        Args:
            messages: Lista de mensajes en formato nativo del LLM
            system_prompt: Prompt del sistema
            tools: Lista de tools disponibles en formato del LLM
            max_tokens: Máximo de tokens
            temperature: Temperatura

        Returns:
            LLMResponse normalizado
        """
        pass

    @abstractmethod
    def format_tools(self, mcp_tools: List) -> List[Dict]:
        """
        Convierte tools MCP al formato específico del LLM.

        Args:
            mcp_tools: Tools en formato MCP

        Returns:
            Tools en formato específico del LLM
        """
        pass

    @abstractmethod
    def create_tool_result_message(self, tool_results: List[Dict]) -> Dict:
        """
        Crea mensaje con resultados de tools en formato del LLM.

        Args:
            tool_results: Lista de resultados de tools

        Returns:
            Mensaje en formato del LLM
        """
        pass

    @abstractmethod
    def serialize_assistant_message(self, raw_content: Any) -> Dict:
        """
        Serializa mensaje del asistente para agregar al historial.

        Args:
            raw_content: Contenido raw del LLM

        Returns:
            Mensaje serializado para historial
        """
        pass
