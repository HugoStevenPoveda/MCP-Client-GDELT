"""
Construction handler for executing and tracking construction phase tools.
Manages the 3-step construction workflow.
"""

from typing import Any
from loguru import logger

from cliente_mcp.core.storage import ConversationStore
from cliente_mcp.validators.tool_classifier import ToolClassifier


class ConstructionHandler:
    """
    Handles execution of construction tools.
    Tracks progress through the 3-step construction phase.
    """

    def __init__(self, store: ConversationStore, classifier: ToolClassifier):
        """
        Initialize the construction handler.

        Args:
            store: ConversationStore for tracking construction status
            classifier: ToolClassifier for getting tool information
        """
        self.store = store
        self.classifier = classifier

    async def execute(
        self,
        tool_name: str,
        params: dict,
        mcp_client
    ) -> Any:
        """
        Execute a construction tool and track its completion.

        Args:
            tool_name: Name of the construction tool
            params: Parameters for the tool
            mcp_client: MCP client to execute the tool

        Returns:
            Result from the tool execution (passed through unchanged)
        """
        logger.info(f"🔨 Executing construction tool: {tool_name}")

        # Execute the tool via MCP client
        try:
            async with mcp_client:
                result = await mcp_client.call_tool(tool_name, params)
                result_str = str(result)

            logger.info(f"✓ Construction tool executed: {tool_name}")
            logger.debug(f"   Result: {result_str[:200]}...")

            # Mark as complete in storage
            self.store.mark_construction_complete(tool_name, result)

            # Log progress
            step = self.classifier.get_construction_step(tool_name)
            progress = self.get_progress_message()
            logger.info(f"📊 Construction progress: {progress} | Step {step}/3 completed")

            # Check if construction is fully complete
            if self.store.is_construction_complete():
                logger.info("✅ Construction phase COMPLETE - All 3 steps done!")

            return result_str

        except Exception as e:
            logger.error(f"❌ Error executing construction tool '{tool_name}': {e}")
            raise

    def get_progress_message(self) -> str:
        """
        Get a progress message for construction phase.

        Returns:
            Progress string like "2/3 completed"
        """
        status = self.store.get_construction_status()

        # Count how many unique steps are completed
        completed_steps = set()
        for construction_status in status.values():
            if construction_status.completed and construction_status.step:
                completed_steps.add(construction_status.step)

        completed_count = len(completed_steps)
        return f"{completed_count}/3 completed"

    def get_missing_steps(self) -> list:
        """
        Get list of missing construction steps.

        Returns:
            List of step numbers that are not yet completed
        """
        status = self.store.get_construction_status()

        completed_steps = set()
        for construction_status in status.values():
            if construction_status.completed and construction_status.step:
                completed_steps.add(construction_status.step)

        all_steps = {1, 2, 3}
        missing = all_steps - completed_steps

        return sorted(missing)

    def is_complete(self) -> bool:
        """
        Check if construction phase is complete.

        Returns:
            True if all 3 construction steps are done
        """
        return self.store.is_construction_complete()

    def __repr__(self) -> str:
        progress = self.get_progress_message()
        return f"ConstructionHandler(progress={progress}, complete={self.is_complete()})"
