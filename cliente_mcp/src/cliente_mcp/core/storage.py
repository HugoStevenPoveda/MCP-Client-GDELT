"""
Conversation storage for caching construction status and query results.
Provides a local in-memory cache that can be easily replaced with Redis in the future.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid

from .models import (
    QueryCacheEntry,
    ConstructionStatus,
    PreconsultaStatus,
    ConversationMetadata
)
from .config import TOOL_CONFIG


class ConversationStore:
    """
    In-memory storage for conversation state.
    Tracks construction progress and caches query results.
    """

    def __init__(self, conversation_id: Optional[str] = None):
        """
        Initialize the conversation store.

        Args:
            conversation_id: Unique ID for this conversation. Auto-generated if not provided.
        """
        self.conversation_id = conversation_id or str(uuid.uuid4())[:8]

        # Track construction status: {tool_name: ConstructionStatus}
        self._construction_status: Dict[str, ConstructionStatus] = {}

        # Track preconsulta status: {tool_name: PreconsultaStatus}
        self._preconsulta_status: Dict[str, PreconsultaStatus] = {}

        # Cache query results: {tool_name: [QueryCacheEntry, ...]}
        # Using list to support multiple calls to the same tool with different params
        self._query_cache: Dict[str, List[QueryCacheEntry]] = {}

        # Track query attempts (including failures): {tool_name: num_attempts}
        self._query_attempts: Dict[str, int] = {}

        # Neo4j query tool names
        self.NEO4J_QUERIES = {
            "query_by_gkg_record_id",
            "query_relations_for_tail",
            "query_relations_for_head"
        }

        # Bypass flag: salta PRECONSULTA y QUERY, va directo a SÍNTESIS tras CONSTRUCCIÓN
        self.skip_intermediate_phases: bool = False

        # Metadata
        self.metadata = ConversationMetadata(
            conversation_id=self.conversation_id
        )

    # ==================== CONSTRUCTION METHODS ====================

    def mark_construction_complete(self, tool_name: str, result: Any) -> None:
        """
        Mark a construction tool as completed.

        Args:
            tool_name: Name of the construction tool
            result: Result returned by the tool
        """
        step = TOOL_CONFIG.get_construction_step(tool_name)

        self._construction_status[tool_name] = ConstructionStatus(
            tool_name=tool_name,
            completed=True,
            result=result,
            timestamp=datetime.now(),
            step=step
        )

    def is_construction_complete(self) -> bool:
        """
        Check if all required construction steps are complete.

        Returns:
            True if at least one tool from each step (1, 2, 3) has been completed
        """
        completed_steps = set()

        for status in self._construction_status.values():
            if status.completed and status.step:
                completed_steps.add(status.step)

        # Need all 3 steps completed
        return completed_steps == {1, 2, 3}

    def get_missing_construction_tools(self) -> List[str]:
        """
        Get list of construction steps that are still pending.

        Returns:
            List of tool names representing missing steps
        """
        completed_steps = set()

        for status in self._construction_status.values():
            if status.completed and status.step:
                completed_steps.add(status.step)

        missing_steps = {1, 2, 3} - completed_steps

        # Return one tool name per missing step
        missing_tools = []
        for step in sorted(missing_steps):
            # Find first tool for this step
            for tool_name, tool_step in TOOL_CONFIG.construction_tools.items():
                if tool_step == step:
                    missing_tools.append(tool_name)
                    break

        return missing_tools

    def get_construction_status(self) -> Dict[str, ConstructionStatus]:
        """Get all construction statuses."""
        return self._construction_status.copy()

    # ==================== PRECONSULTA METHODS ====================

    def mark_preconsulta_complete(self, tool_name: str, result: Any) -> None:
        """
        Mark a preconsulta tool as completed.

        Args:
            tool_name: Name of the preconsulta tool
            result: Result returned by the tool
        """
        self._preconsulta_status[tool_name] = PreconsultaStatus(
            tool_name=tool_name,
            completed=True,
            result=result,
            timestamp=datetime.now()
        )

    def is_preconsulta_complete(self) -> bool:
        """
        Check if all required preconsulta tools are complete.

        Returns:
            True if all 3 preconsulta tools have been completed
        """
        required_tools = set(TOOL_CONFIG.get_all_preconsulta_tools())
        completed_tools = set()

        for status in self._preconsulta_status.values():
            if status.completed:
                completed_tools.add(status.tool_name)

        # Need all preconsulta tools completed
        return required_tools.issubset(completed_tools)

    def get_missing_preconsulta_tools(self) -> List[str]:
        """
        Get list of preconsulta tools that are still pending.

        Returns:
            List of tool names that haven't been completed
        """
        required_tools = set(TOOL_CONFIG.get_all_preconsulta_tools())
        completed_tools = set()

        for status in self._preconsulta_status.values():
            if status.completed:
                completed_tools.add(status.tool_name)

        missing_tools = required_tools - completed_tools
        return list(missing_tools)

    def get_preconsulta_status(self) -> Dict[str, PreconsultaStatus]:
        """Get all preconsulta statuses."""
        return self._preconsulta_status.copy()

    # ==================== QUERY METHODS ====================

    def add_query_result(self, tool_name: str, params: dict, result: Any) -> None:
        """
        Add a query result to the cache.

        Args:
            tool_name: Name of the query tool
            params: Parameters used for the query
            result: Result returned by the tool
        """
        entry = QueryCacheEntry(
            tool_name=tool_name,
            params=params,
            result=result,
            timestamp=datetime.now()
        )

        if tool_name not in self._query_cache:
            self._query_cache[tool_name] = []

        self._query_cache[tool_name].append(entry)

        # Update metadata
        self.metadata.total_queries = self.get_query_count()

    def get_all_queries(self) -> List[QueryCacheEntry]:
        """
        Get all cached query results.

        Returns:
            List of all QueryCacheEntry objects, ordered by timestamp
        """
        all_queries = []
        for entries in self._query_cache.values():
            all_queries.extend(entries)

        # Sort by timestamp
        all_queries.sort(key=lambda x: x.timestamp)

        return all_queries

    def get_queries_by_tool(self, tool_name: str) -> List[QueryCacheEntry]:
        """
        Get all queries for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            List of QueryCacheEntry for that tool
        """
        return self._query_cache.get(tool_name, []).copy()

    def get_query_count(self) -> int:
        """Get total number of queries executed."""
        return sum(len(entries) for entries in self._query_cache.values())

    def record_query_attempt(self, tool_name: str) -> None:
        """
        Record an attempt to execute a query (success or failure).

        Args:
            tool_name: Name of the query tool
        """
        self._query_attempts[tool_name] = self._query_attempts.get(tool_name, 0) + 1

    def get_attempt_count(self, tool_name: str) -> int:
        """
        Get the number of attempts for a specific query tool.

        Args:
            tool_name: Name of the query tool

        Returns:
            Number of attempts (0 if never attempted)
        """
        return self._query_attempts.get(tool_name, 0)

    def has_attempted_neo4j(self) -> bool:
        """
        Check if at least one Neo4j query has been attempted.

        Returns:
            True if any Neo4j query has been attempted
        """
        return any(q in self._query_attempts for q in self.NEO4J_QUERIES)

    def get_attempted_queries(self) -> List[str]:
        """
        Get list of all query tools that have been attempted.

        Returns:
            List of query tool names
        """
        return list(self._query_attempts.keys())

    def get_all_queries_as_unified_json(self) -> dict:
        """
        Get all cached query results in a single unified JSON structure.

        Returns:
            Dictionary with all queries grouped by tool name with their results
        """
        unified = {
            "metadata": {
                "conversation_id": self.conversation_id,
                "user_question": self.metadata.user_question,
                "total_queries": self.get_query_count(),
                "timestamp": datetime.now().isoformat()
            },
            "queries_by_tool": {},
            "all_queries_ordered": []
        }

        # Group by tool
        for tool_name, entries in self._query_cache.items():
            unified["queries_by_tool"][tool_name] = [
                {
                    "params": entry.params,
                    "result": entry.result,
                    "timestamp": entry.timestamp.isoformat()
                }
                for entry in entries
            ]

        # All queries in chronological order
        all_queries = self.get_all_queries()
        unified["all_queries_ordered"] = [
            {
                "tool_name": entry.tool_name,
                "params": entry.params,
                "result": entry.result,
                "timestamp": entry.timestamp.isoformat()
            }
            for entry in all_queries
        ]

        return unified

    # ==================== SUMMARY METHODS ====================

    def get_summary(self) -> dict:
        """
        Get a complete summary of the conversation state.

        Returns:
            Dictionary with construction status, preconsulta status, queries, and metadata
        """
        return {
            "conversation_id": self.conversation_id,
            "metadata": self.metadata.to_dict(),
            "construction": {
                "completed": self.is_construction_complete(),
                "status": {
                    name: status.to_dict()
                    for name, status in self._construction_status.items()
                },
                "missing_tools": self.get_missing_construction_tools()
            },
            "preconsulta": {
                "completed": self.is_preconsulta_complete(),
                "status": {
                    name: status.to_dict()
                    for name, status in self._preconsulta_status.items()
                },
                "missing_tools": self.get_missing_preconsulta_tools()
            },
            "queries": {
                "total_count": self.get_query_count(),
                "by_tool": {
                    tool: [entry.to_dict() for entry in entries]
                    for tool, entries in self._query_cache.items()
                }
            }
        }

    # ==================== UTILITY METHODS ====================

    def reset(self) -> None:
        """Reset all state, keeping the same conversation_id."""
        self._construction_status.clear()
        self._preconsulta_status.clear()
        self._query_cache.clear()
        self._query_attempts.clear()
        self.metadata = ConversationMetadata(
            conversation_id=self.conversation_id
        )

    def set_user_question(self, question: str) -> None:
        """Set the user's initial question in metadata."""
        self.metadata.user_question = question

    def export_preconsulta_to_json(self, output_path: str = "logs/preconsulta.json") -> dict:
        """
        Export preconsulta results to a JSON file (simplified structure).

        Args:
            output_path: Path to save the JSON file

        Returns:
            Dictionary with preconsulta data
        """
        import json
        import os

        # Simplified structure: just tool_name -> result
        preconsulta_data = {}

        # Add each preconsulta tool result (clean, no metadata)
        for tool_name, status in self._preconsulta_status.items():
            if status.completed:
                # Store only the result, no timestamps or metadata
                preconsulta_data[tool_name] = status.result

        # Create logs directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(preconsulta_data, f, indent=2, ensure_ascii=False)

        return preconsulta_data

    def export_queries_to_json(self, output_path: str = "logs/queries.json") -> dict:
        """
        Export all query results to a JSON file (incrementally updated).

        Args:
            output_path: Path to save the JSON file

        Returns:
            Dictionary with all query data
        """
        import json
        import os

        queries_data = self.get_all_queries_as_unified_json()

        # Create logs directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(queries_data, f, indent=2, ensure_ascii=False)

        return queries_data

    def __repr__(self) -> str:
        return (
            f"ConversationStore(id={self.conversation_id}, "
            f"construction_complete={self.is_construction_complete()}, "
            f"queries={self.get_query_count()})"
        )
