"""
Tool classifier for categorizing MCP tools.
Determines if a tool is construction, query, synthetic, etc.
"""

from typing import Optional
from cliente_mcp.core.config import ToolConfig
from cliente_mcp.core.models import ToolType


class ToolClassifier:
    """
    Classifies tools based on their type and purpose.
    Stateless class that only queries configuration.
    """

    def __init__(self, config: ToolConfig):
        """
        Initialize the tool classifier.

        Args:
            config: ToolConfig instance with tool definitions
        """
        self.config = config

    def is_construction_tool(self, tool_name: str) -> bool:
        """
        Check if a tool is a construction tool.

        Args:
            tool_name: Name of the tool

        Returns:
            True if the tool is a construction tool
        """
        return self.config.is_construction_tool(tool_name)

    def is_preconsulta_tool(self, tool_name: str) -> bool:
        """
        Check if a tool is a preconsulta tool.

        Args:
            tool_name: Name of the tool

        Returns:
            True if the tool is a preconsulta tool
        """
        return self.config.is_preconsulta_tool(tool_name)

    def is_query_tool(self, tool_name: str) -> bool:
        """
        Check if a tool is a query tool.

        Args:
            tool_name: Name of the tool

        Returns:
            True if the tool is a query tool
        """
        return self.config.is_query_tool(tool_name)

    def is_update_tool(self, tool_name: str) -> bool:
        """
        Check if a tool is an update tool.

        Args:
            tool_name: Name of the tool

        Returns:
            True if the tool is an update tool
        """
        return self.config.is_update_tool(tool_name)

    def is_synthetic_tool(self, tool_name: str) -> bool:
        """
        Check if a tool is a synthetic (client-side) tool.

        Args:
            tool_name: Name of the tool

        Returns:
            True if the tool is a synthetic tool
        """
        return self.config.is_synthetic_tool(tool_name)

    def is_utility_tool(self, tool_name: str) -> bool:
        """
        Check if a tool is a utility tool.

        Args:
            tool_name: Name of the tool

        Returns:
            True if the tool is a utility tool
        """
        return self.config.is_utility_tool(tool_name)

    def get_tool_type(self, tool_name: str) -> ToolType:
        """
        Get the type of a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            ToolType enum value
        """
        if self.is_construction_tool(tool_name):
            return ToolType.CONSTRUCTION
        elif self.is_preconsulta_tool(tool_name):
            return ToolType.PRECONSULTA
        elif self.is_query_tool(tool_name):
            return ToolType.QUERY
        elif self.is_synthetic_tool(tool_name):
            return ToolType.SYNTHETIC
        elif self.is_update_tool(tool_name):
            # Treat update tools as query tools for now
            return ToolType.QUERY
        elif self.is_utility_tool(tool_name):
            # Utility tools don't affect workflow
            return ToolType.QUERY
        else:
            return ToolType.UNKNOWN

    def get_construction_step(self, tool_name: str) -> Optional[int]:
        """
        Get the construction step number (1, 2, or 3) for a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Step number (1-3) or None if not a construction tool
        """
        return self.config.get_construction_step(tool_name)

    def requires_construction(self, tool_name: str) -> bool:
        """
        Check if a tool requires construction to be complete before execution.

        Args:
            tool_name: Name of the tool

        Returns:
            True if the tool requires construction to be complete
        """
        tool_type = self.get_tool_type(tool_name)
        return tool_type in [ToolType.PRECONSULTA, ToolType.QUERY, ToolType.SYNTHETIC]

    def __repr__(self) -> str:
        return f"ToolClassifier(construction={len(self.config.construction_tools)}, query={len(self.config.query_tools)})"
