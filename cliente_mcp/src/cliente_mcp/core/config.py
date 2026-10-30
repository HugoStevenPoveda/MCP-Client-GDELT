"""
Configuration for tool classification.
Defines which tools belong to construction, query, or synthetic categories.
"""

from typing import Dict, List, Optional


# ==================== CONSTRUCTION TOOLS ====================
# These tools must be executed in order before any query can be performed
CONSTRUCTION_TOOLS: Dict[str, int] = {
    # Step 1: Update GDELT data
    "update_gdelt_data": 1,

    # Step 2: Extract knowledge graph (any variant)
    "extract_knowledge_graph": 2,

    # Step 3: Train initial embeddings
    "initial_fit_model": 3,
}


# ==================== PRECONSULTA TOOLS ====================
# These tools must be executed after construction and before queries
# They gather metadata and context from the system
PRECONSULTA_TOOLS: List[str] = [
    "get_tipos_relaciones",        # Get available relation types from Neo4j
    "get_record_ids_recientes",    # Get recent record IDs (last 30 minutes)
    "query_by_gkg_record_id",      # Extract tripletas from recent documents (batch execution)
    "query_gdelt_data",            # Get general GDELT events for context (last 15 minutes)
]


# ==================== QUERY TOOLS ====================
# These tools can only be executed after construction AND preconsulta are complete
QUERY_TOOLS: List[str] = [
    # GDELT queries (query_gdelt_data también puede usarse aquí opcionalmente)
    "query_gdelt_data",
    "query_gdelt_data_by_country",
    "query_gdelt_data_by_two_countries",

    # Embedding queries (OBLIGATORIAS en Fase 2)
    "discover_top_n",
    "discover_plausible_triplets",

    # Neo4j queries (al menos 1 OBLIGATORIA en Fase 2)
    "query_by_gkg_record_id",
    "query_relations_for_tail",
    "query_relations_for_head",
]


# ==================== UPDATE TOOLS ====================
# These tools update the system after construction
UPDATE_TOOLS: List[str] = [
    "incremental_fit_model",
]


# ==================== SYNTHETIC TOOLS ====================
# These are client-side tools that don't call MCP servers
SYNTHETIC_TOOLS: List[str] = [
    "synthesize_final_response",
]


# ==================== UTILITY TOOLS ====================
# These are informational tools that don't affect workflow
UTILITY_TOOLS: List[str] = [
]


# ==================== CONFIGURATION CLASS ====================
class ToolConfig:
    """Configuration for tool classification and workflow."""

    def __init__(self):
        self.construction_tools = CONSTRUCTION_TOOLS
        self.preconsulta_tools = PRECONSULTA_TOOLS
        self.query_tools = QUERY_TOOLS
        self.update_tools = UPDATE_TOOLS
        self.synthetic_tools = SYNTHETIC_TOOLS
        self.utility_tools = UTILITY_TOOLS

    def get_construction_step(self, tool_name: str) -> Optional[int]:
        """Get the construction step number (1, 2, or 3) for a tool."""
        return self.construction_tools.get(tool_name)

    def is_construction_tool(self, tool_name: str) -> bool:
        """Check if a tool is a construction tool."""
        return tool_name in self.construction_tools

    def is_preconsulta_tool(self, tool_name: str) -> bool:
        """Check if a tool is a preconsulta tool."""
        return tool_name in self.preconsulta_tools

    def is_query_tool(self, tool_name: str) -> bool:
        """Check if a tool is a query tool."""
        return tool_name in self.query_tools

    def is_update_tool(self, tool_name: str) -> bool:
        """Check if a tool is an update tool."""
        return tool_name in self.update_tools

    def is_synthetic_tool(self, tool_name: str) -> bool:
        """Check if a tool is a synthetic (client-side) tool."""
        return tool_name in self.synthetic_tools

    def is_utility_tool(self, tool_name: str) -> bool:
        """Check if a tool is a utility tool."""
        return tool_name in self.utility_tools

    def get_all_construction_tools(self) -> List[str]:
        """Get list of all construction tool names."""
        return list(self.construction_tools.keys())

    def get_required_construction_tools(self) -> List[str]:
        """
        Get the minimum required construction tools (one per step).
        Returns the first tool of each step.
        """
        tools_by_step = {}
        for tool, step in self.construction_tools.items():
            if step not in tools_by_step:
                tools_by_step[step] = tool

        return [tools_by_step[step] for step in sorted(tools_by_step.keys())]

    def get_all_preconsulta_tools(self) -> List[str]:
        """Get list of all preconsulta tool names."""
        return self.preconsulta_tools.copy()


# Global configuration instance
TOOL_CONFIG = ToolConfig()
