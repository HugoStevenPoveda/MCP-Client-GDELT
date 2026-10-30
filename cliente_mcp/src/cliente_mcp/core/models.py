"""
Data models for the MCP client workflow.
Defines the core data structures used across the application.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, List
from enum import Enum


class ToolType(Enum):
    """Enumeration of tool types."""
    CONSTRUCTION = "construction"
    PRECONSULTA = "preconsulta"
    QUERY = "query"
    SYNTHETIC = "synthetic"
    UNKNOWN = "unknown"


@dataclass
class ToolExecutionResult:
    """Result of a tool execution."""
    tool_name: str
    success: bool
    result: Any
    timestamp: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of a tool execution validation."""
    valid: bool
    error_message: Optional[str] = None
    missing_tools: List[str] = field(default_factory=list)


@dataclass
class QueryCacheEntry:
    """Entry in the query cache."""
    tool_name: str
    params: dict
    result: Any
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "tool_name": self.tool_name,
            "params": self.params,
            "result": self.result,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ConstructionStatus:
    """Status of a construction tool execution."""
    tool_name: str
    completed: bool
    result: Any
    timestamp: datetime = field(default_factory=datetime.now)
    step: Optional[int] = None  # 1, 2, or 3

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "tool_name": self.tool_name,
            "completed": self.completed,
            "result": self.result,
            "timestamp": self.timestamp.isoformat(),
            "step": self.step
        }


@dataclass
class PreconsultaStatus:
    """Status of a preconsulta tool execution."""
    tool_name: str
    completed: bool
    result: Any
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "tool_name": self.tool_name,
            "completed": self.completed,
            "result": self.result,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ConversationMetadata:
    """Metadata about a conversation."""
    conversation_id: str
    start_time: datetime = field(default_factory=datetime.now)
    user_question: Optional[str] = None
    total_queries: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "conversation_id": self.conversation_id,
            "start_time": self.start_time.isoformat(),
            "user_question": self.user_question,
            "total_queries": self.total_queries
        }
