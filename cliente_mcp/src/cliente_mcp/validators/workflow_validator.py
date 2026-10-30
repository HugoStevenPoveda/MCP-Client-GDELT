"""
Workflow validator for ensuring correct tool execution order.
Validates that prerequisites are met before executing tools.
"""

from typing import List
from cliente_mcp.core.storage import ConversationStore
from cliente_mcp.core.models import ValidationResult, ToolType
from .tool_classifier import ToolClassifier


class WorkflowValidator:
    """
    Validates tool executions according to workflow rules.
    Ensures construction is complete before queries can run.
    """

    def __init__(self, classifier: ToolClassifier, store: ConversationStore):
        """
        Initialize the workflow validator.

        Args:
            classifier: ToolClassifier instance for determining tool types
            store: ConversationStore instance for checking conversation state
        """
        self.classifier = classifier
        self.store = store

    def validate_execution(self, tool_name: str) -> ValidationResult:
        """
        Validate if a tool can be executed given the current state.

        Args:
            tool_name: Name of the tool to validate

        Returns:
            ValidationResult with validation status and error message if invalid
        """
        tool_type = self.classifier.get_tool_type(tool_name)

        # Construction tools can always be executed
        if tool_type == ToolType.CONSTRUCTION:
            return ValidationResult(valid=True)

        # Utility tools can always be executed
        if self.classifier.is_utility_tool(tool_name):
            return ValidationResult(valid=True)

        # Update tools can be executed if construction is complete
        if self.classifier.is_update_tool(tool_name):
            if not self.store.is_construction_complete():
                missing = self.store.get_missing_construction_tools()
                return ValidationResult(
                    valid=False,
                    error_message=(
                        f"Cannot execute '{tool_name}': FASE CONSTRUCCIÓN must be "
                        f"completed first. Missing tools: {', '.join(missing)}"
                    ),
                    missing_tools=missing
                )
            return ValidationResult(valid=True)

        # Preconsulta tools require construction to be complete
        if tool_type == ToolType.PRECONSULTA:
            if self.store.skip_intermediate_phases and self.store.is_construction_complete():
                return ValidationResult(
                    valid=False,
                    error_message=(
                        f"MODO BYPASS ACTIVO: No ejecutes '{tool_name}'. "
                        f"Llama directamente a 'synthesize_final_response' para activar el Agente 2."
                    )
                )
            if not self.store.is_construction_complete():
                missing = self.store.get_missing_construction_tools()
                return ValidationResult(
                    valid=False,
                    error_message=(
                        f"Cannot execute '{tool_name}': FASE CONSTRUCCIÓN must be "
                        f"completed first. Missing tools: {', '.join(missing)}"
                    ),
                    missing_tools=missing
                )
            return ValidationResult(valid=True)

        # Query tools require BOTH construction AND preconsulta to be complete
        if tool_type == ToolType.QUERY:
            if self.store.skip_intermediate_phases and self.store.is_construction_complete():
                return ValidationResult(
                    valid=False,
                    error_message=(
                        f"MODO BYPASS ACTIVO: No ejecutes '{tool_name}'. "
                        f"Llama directamente a 'synthesize_final_response' para activar el Agente 2."
                    )
                )
            if not self.store.is_construction_complete():
                missing = self.store.get_missing_construction_tools()
                return ValidationResult(
                    valid=False,
                    error_message=(
                        f"Cannot execute '{tool_name}': FASE CONSTRUCCIÓN must be "
                        f"completed first. Missing tools: {', '.join(missing)}"
                    ),
                    missing_tools=missing
                )

            if not self.store.is_preconsulta_complete():
                missing = self.store.get_missing_preconsulta_tools()
                return ValidationResult(
                    valid=False,
                    error_message=(
                        f"Cannot execute '{tool_name}': FASE PRECONSULTA must be "
                        f"completed first. Missing tools: {', '.join(missing)}"
                    ),
                    missing_tools=missing
                )

            return ValidationResult(valid=True)

        # Synthetic tools (like synthesize) require at least one query
        if tool_type == ToolType.SYNTHETIC:
            if tool_name == "synthesize_final_response":
                if self.store.skip_intermediate_phases and self.store.is_construction_complete():
                    return ValidationResult(valid=True)
                query_count = self.store.get_query_count()
                if query_count == 0:
                    return ValidationResult(
                        valid=False,
                        error_message=(
                            "Cannot synthesize: No queries have been executed yet. "
                            "Execute at least 1-2 query tools first."
                        )
                    )
            return ValidationResult(valid=True)

        # Unknown tool type
        if tool_type == ToolType.UNKNOWN:
            return ValidationResult(
                valid=False,
                error_message=f"Unknown tool: '{tool_name}'"
            )

        # Default: allow execution
        return ValidationResult(valid=True)

    def validate_synthesis_ready(self) -> ValidationResult:
        """
        Validate that required phases are complete before synthesis.

        Required:
        - FASE CONSTRUCCIÓN complete (3 tools)
        - FASE PRECONSULTA complete (4 tools)
        - FASE DE CONSULTAS queries attempted:
          * discover_top_n
          * discover_plausible_triplets
          * At least 1 Neo4j query (query_relations_for_tail, query_relations_for_head)

        Returns:
            ValidationResult indicating if synthesis can proceed
        """
        # Bypass: si skip_intermediate_phases y construcción completa, síntesis habilitada
        if self.store.skip_intermediate_phases and self.store.is_construction_complete():
            return ValidationResult(valid=True)

        # First validate that PRECONSULTA is complete
        if not self.store.is_preconsulta_complete():
            missing = self.store.get_missing_preconsulta_tools()
            return ValidationResult(
                valid=False,
                error_message=(
                    f"Cannot execute 'synthesize_final_response': FASE PRECONSULTA "
                    f"incompleta. Missing tools: {', '.join(missing)}. "
                    f"Debes ejecutar estos tools obligatorios primero."
                ),
                missing_tools=missing
            )

        # Then validate that required queries have been attempted
        attempted = self.store.get_attempted_queries()
        missing = []

        # Check discover_top_n
        if "discover_top_n" not in attempted:
            missing.append("discover_top_n")

        # Check discover_plausible_triplets
        if "discover_plausible_triplets" not in attempted:
            missing.append("discover_plausible_triplets")

        # Check at least 1 Neo4j query
        if not self.store.has_attempted_neo4j():
            missing.append("al menos 1 consulta Neo4j (query_by_gkg_record_id, query_relations_for_tail, query_relations_for_head)")

        if missing:
            return ValidationResult(
                valid=False,
                error_message=(
                    f"Cannot execute 'synthesize_final_response': Fase 2 incompleta. "
                    f"Debes intentar las siguientes consultas obligatorias: {', '.join(missing)}. "
                    f"Nota: No importa si fallan, pero debes intentar ejecutarlas."
                ),
                missing_tools=missing
            )

        return ValidationResult(valid=True)

    def check_prerequisites(self, tool_name: str) -> List[str]:
        """
        Get list of tools that must be executed before this tool.

        Args:
            tool_name: Name of the tool

        Returns:
            List of prerequisite tool names
        """
        tool_type = self.classifier.get_tool_type(tool_name)

        if tool_type in [ToolType.QUERY, ToolType.SYNTHETIC]:
            # If construction is not complete, return missing construction tools
            if not self.store.is_construction_complete():
                return self.store.get_missing_construction_tools()

        return []

    def get_workflow_status(self) -> dict:
        """
        Get current workflow status.

        Returns:
            Dictionary with workflow state information
        """
        return {
            "construction_complete": self.store.is_construction_complete(),
            "preconsulta_complete": self.store.is_preconsulta_complete(),
            "queries_executed": self.store.get_query_count(),
            "missing_construction_tools": self.store.get_missing_construction_tools(),
            "missing_preconsulta_tools": self.store.get_missing_preconsulta_tools(),
            "can_execute_preconsulta": self.store.is_construction_complete(),
            "can_execute_queries": self.store.is_construction_complete() and self.store.is_preconsulta_complete(),
            "can_synthesize": self.store.is_preconsulta_complete() and self.store.get_query_count() > 0
        }

    def __repr__(self) -> str:
        status = self.get_workflow_status()
        return (
            f"WorkflowValidator(construction_complete={status['construction_complete']}, "
            f"queries={status['queries_executed']})"
        )
