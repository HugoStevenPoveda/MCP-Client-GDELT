"""
Synthesis handler for generating final responses with accumulated data.
Combines all cached query results into a structured prompt.
"""

import json
from pathlib import Path
from typing import Dict
from loguru import logger

from cliente_mcp.core.storage import ConversationStore
from cliente_mcp.core.models import ValidationResult
from cliente_mcp.templates.synthesis_template import SynthesisTemplateBuilder


class SynthesisHandler:
    """
    Handles the synthetic 'synthesize_final_response' tool.
    Generates a structured prompt with all accumulated query results.
    """

    def __init__(
        self,
        store: ConversationStore,
        template_builder: SynthesisTemplateBuilder
    ):
        """
        Initialize the synthesis handler.

        Args:
            store: ConversationStore with cached queries
            template_builder: SynthesisTemplateBuilder for generating prompts
        """
        self.store = store
        self.template_builder = template_builder

    def execute(self, params: Dict) -> str:
        """
        Execute the synthesis process.

        Args:
            params: Parameters from the tool call (typically just confirmation)

        Returns:
            Formatted prompt with all accumulated data
        """
        logger.info("🎯 Executing synthesis - gathering all cached data")

        # Validate readiness
        validation = self.validate_readiness()
        if not validation.valid:
            logger.warning(f"⚠️  Synthesis validation failed: {validation.error_message}")
            return validation.error_message

        # Load preconsulta data from JSON file
        preconsulta_data = self._load_preconsulta_json()
        if preconsulta_data:
            logger.info("📋 Preconsulta data loaded from preconsulta.json")
        else:
            logger.warning("⚠️  No preconsulta data found")

        # Load queries data from JSON file (already saved incrementally)
        queries_data = self._load_queries_json()
        if queries_data:
            query_count = queries_data["metadata"]["total_queries"]
            logger.info(f"📊 Queries data loaded from queries.json ({query_count} queries)")
        else:
            logger.warning("⚠️  No queries data found in queries.json")
            query_count = 0

        logger.info(f"📊 Synthesizing {query_count} queries")

        # Get all queries for template building (from store)
        queries = self.store.get_all_queries()

        # Build the synthesis prompt with preconsulta data
        synthesis_prompt = self.template_builder.build(
            queries=queries,
            metadata=self.store.metadata,
            preconsulta_data=preconsulta_data
        )

        logger.info(f"✓ Synthesis prompt generated ({len(synthesis_prompt)} chars)")
        logger.debug(f"   Prompt preview: {synthesis_prompt[:300]}...")

        return synthesis_prompt

    def _load_preconsulta_json(self) -> dict:
        """
        Load preconsulta data from JSON file.

        Returns:
            Dictionary with preconsulta data, or None if file doesn't exist
        """
        preconsulta_path = Path("logs/preconsulta.json")

        if not preconsulta_path.exists():
            return None

        try:
            with open(preconsulta_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.debug(f"   Preconsulta file: {preconsulta_path.absolute()}")
                logger.debug(f"   Size: {preconsulta_path.stat().st_size} bytes")
                return data
        except Exception as e:
            logger.error(f"❌ Error loading preconsulta.json: {e}")
            return None

    def _load_queries_json(self) -> dict:
        """
        Load queries data from JSON file.

        Returns:
            Dictionary with queries data, or None if file doesn't exist
        """
        queries_path = Path("logs/queries.json")

        if not queries_path.exists():
            return None

        try:
            with open(queries_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.debug(f"   Queries file: {queries_path.absolute()}")
                logger.debug(f"   Size: {queries_path.stat().st_size} bytes")
                return data
        except Exception as e:
            logger.error(f"❌ Error loading queries.json: {e}")
            return None

    def validate_readiness(self) -> ValidationResult:
        """
        Validate that synthesis is ready to be performed.

        Returns:
            ValidationResult indicating if synthesis can proceed
        """
        query_count = self.store.get_query_count()

        if query_count == 0:
            return ValidationResult(
                valid=False,
                error_message=(
                    "❌ No se puede sintetizar: No hay consultas acumuladas. "
                    "Ejecuta al menos 1-2 query tools primero."
                )
            )

        # Optional: warn if too few queries
        if query_count < 2:
            logger.warning(
                f"⚠️  Solo {query_count} consulta acumulada. "
                "Considera ejecutar más consultas para una respuesta más completa."
            )

        return ValidationResult(valid=True)

    def get_synthesis_preview(self) -> dict:
        """
        Get a preview of what will be synthesized.

        Returns:
            Dictionary with synthesis information
        """
        queries = self.store.get_all_queries()

        return {
            "ready": self.validate_readiness().valid,
            "query_count": len(queries),
            "queries": [
                {
                    "tool": q.tool_name,
                    "timestamp": q.timestamp.isoformat(),
                    "params": q.params
                }
                for q in queries
            ],
            "metadata": self.store.metadata.to_dict()
        }

    def __repr__(self) -> str:
        query_count = self.store.get_query_count()
        ready = self.validate_readiness().valid
        return f"SynthesisHandler(queries={query_count}, ready={ready})"
