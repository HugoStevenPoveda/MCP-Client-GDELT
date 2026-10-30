"""
Synthetic tools provider.
Defines client-side tools that don't call MCP servers.
"""

from typing import Dict, List


def get_synthesize_tool_definition() -> Dict:
    """
    Get the tool definition for 'synthesize_final_response'.

    This is a synthetic tool that doesn't call any MCP server.
    It's handled entirely by the client to gather cached query results.

    Returns:
        Tool definition dictionary in Claude's expected format
    """
    return {
        "name": "synthesize_final_response",
        "description": (
            "Llama esta tool cuando hayas recolectado TODAS las consultas necesarias "
            "para responder completamente al usuario. Esta tool te devolverá todos los "
            "resultados de las consultas ejecutadas en un formato estructurado. "
            "\n\n"
            "CUÁNDO USAR:\n"
            "- Después de ejecutar 2-4 consultas relevantes (dependiendo de la complejidad)\n"
            "- Cuando tengas suficiente información para generar una respuesta completa\n"
            "- NO uses esta tool si solo has ejecutado 1 consulta simple\n"
            "\n"
            "QUÉ ESPERAR:\n"
            "- Recibirás todos los resultados de consultas en formato detallado\n"
            "- Podrás usarlos para generar tu respuesta final al usuario\n"
            "- Los datos incluirán parámetros y resultados completos de cada consulta"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ready_to_synthesize": {
                    "type": "boolean",
                    "description": (
                        "Confirma que estás listo para recibir todos los datos acumulados. "
                        "Debe ser 'true'."
                    )
                }
            },
            "required": ["ready_to_synthesize"]
        }
    }


def get_all_synthetic_tools() -> List[Dict]:
    """
    Get all synthetic tool definitions.

    Returns:
        List of tool definition dictionaries
    """
    return [
        get_synthesize_tool_definition()
    ]


def is_synthetic_tool(tool_name: str) -> bool:
    """
    Check if a tool name corresponds to a synthetic tool.

    Args:
        tool_name: Name of the tool to check

    Returns:
        True if the tool is synthetic (client-side)
    """
    synthetic_names = {"synthesize_final_response"}
    return tool_name in synthetic_names
