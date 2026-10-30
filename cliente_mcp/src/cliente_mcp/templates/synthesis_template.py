"""
Template builder for synthesis responses.
Generates structured prompts with accumulated query results.
"""

from typing import List, Dict, Any
from cliente_mcp.core.models import QueryCacheEntry, ConversationMetadata


class SynthesisTemplateBuilder:
    """
    Builds synthesis prompts with accumulated query results.
    Creates a structured template for Claude to generate final responses.
    """

    def __init__(self, max_result_chars: int = 1000):
        """
        Initialize the template builder.

        Args:
            max_result_chars: Maximum characters to include from each query result
        """
        self.max_result_chars = max_result_chars

    def build(
        self,
        queries: List[QueryCacheEntry],
        metadata: ConversationMetadata,
        preconsulta_data: Dict = None
    ) -> str:
        """
        Build the synthesis prompt with all accumulated data.

        Args:
            queries: List of query cache entries
            metadata: Conversation metadata
            preconsulta_data: Preconsulta results from JSON file (optional)

        Returns:
            Formatted prompt string for Claude
        """
        query_count = len(queries)
        user_question = metadata.user_question or "la pregunta del usuario"

        # Build header
        template_parts = [
            "=" * 80,
            "DATOS RECOLECTADOS PARA SÍNTESIS",
            "=" * 80,
            "",
            f"Has ejecutado {query_count} consulta(s) para responder:",
            f'"{user_question}"',
            "",
            "A continuación recibirás todos los resultados en formato estructurado.",
            "",
        ]

        # Add preconsulta data if available
        if preconsulta_data:
            template_parts.extend(self._format_preconsulta_section(preconsulta_data))
            template_parts.append("")

        # Add each query result
        template_parts.append("RESULTADOS DE CONSULTAS:")
        template_parts.append("=" * 80)
        template_parts.append("")

        for idx, query in enumerate(queries, 1):
            template_parts.extend(self._format_query(idx, query))
            template_parts.append("")

        # Add instructions
        template_parts.extend([
            "=" * 80,
            "INSTRUCCIONES PARA GENERAR LA RESPUESTA FINAL:",
            "=" * 80,
            "",
            "Con los datos anteriores, genera una respuesta clara y estructurada que:",
            "",
            "1. Resume los hallazgos principales de todas las consultas",
            "2. Identifica relaciones clave entre entidades",
            "3. Proporciona insights o patrones detectados",
            "4. Ofrece una conclusión útil al usuario",
            "",
            "Responde de forma natural y conversacional, sin mencionar los nombres",
            "técnicos de las tools. Enfócate en el contenido y los hallazgos.",
            "",
            "=" * 80,
        ])

        return "\n".join(template_parts)

    def _format_preconsulta_section(self, preconsulta_data: Dict) -> List[str]:
        """
        Format the preconsulta data section.

        Args:
            preconsulta_data: Dictionary with preconsulta results

        Returns:
            List of formatted strings
        """
        lines = [
            "DATOS DE PRECONSULTA (Contexto del Sistema):",
            "=" * 80,
            ""
        ]

        results = preconsulta_data.get("results", {})

        # Format each preconsulta tool result
        for tool_name, data in results.items():
            lines.append(f"• {tool_name}:")

            result = data.get("result", "")
            result_str = self._format_result(result)

            # Indent result lines
            for line in result_str.split('\n')[:50]:  # Limit lines
                lines.append(f"  {line}")

            lines.append("")

        lines.append("-" * 80)

        return lines

    def _format_query(self, index: int, query: QueryCacheEntry) -> List[str]:
        """
        Format a single query result.

        Args:
            index: Query number (1-based)
            query: QueryCacheEntry to format

        Returns:
            List of formatted strings
        """
        lines = [
            f"[{index}] Tool: {query.tool_name}",
            f"    Timestamp: {query.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        ]

        # Add parameters if present
        if query.params:
            lines.append(f"    Parámetros: {self._format_params(query.params)}")

        # Add result (truncated if needed)
        result_str = self._format_result(query.result)
        if len(result_str) > self.max_result_chars:
            result_str = result_str[:self.max_result_chars] + "... (truncado)"

        lines.append(f"    Resultado:")
        # Indent result lines
        for line in result_str.split('\n'):
            lines.append(f"      {line}")

        lines.append("-" * 80)

        return lines

    def _format_params(self, params: Dict[str, Any]) -> str:
        """
        Format query parameters.

        Args:
            params: Parameters dictionary

        Returns:
            Formatted string
        """
        if not params:
            return "ninguno"

        param_strs = [f"{k}={v}" for k, v in params.items()]
        return ", ".join(param_strs)

    def _format_result(self, result: Any) -> str:
        """
        Format a query result for display.

        Args:
            result: Result to format (can be any type)

        Returns:
            Formatted string
        """
        if result is None:
            return "null"

        # If it's already a string, return as-is
        if isinstance(result, str):
            return result

        # If it's a dict or list, try to format nicely
        if isinstance(result, (dict, list)):
            try:
                import json
                return json.dumps(result, indent=2, ensure_ascii=False)
            except Exception:
                return str(result)

        # Default: convert to string
        return str(result)

    def build_simple(self, queries: List[QueryCacheEntry]) -> str:
        """
        Build a simple synthesis prompt (minimal version).

        Args:
            queries: List of query cache entries

        Returns:
            Simple formatted prompt string
        """
        lines = [
            f"Has ejecutado {len(queries)} consultas. Datos acumulados:",
            ""
        ]

        for idx, query in enumerate(queries, 1):
            result_preview = str(query.result)[:200]
            lines.append(f"{idx}. {query.tool_name}: {result_preview}...")

        lines.append("")
        lines.append("Genera una respuesta final con estos datos.")

        return "\n".join(lines)
