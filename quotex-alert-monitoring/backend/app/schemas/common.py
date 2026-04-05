"""
Common / shared Pydantic v2 models.
ALERT-ONLY monitoring dashboard - no trade execution.
"""

from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""
    items: List[T] = Field(default_factory=list)
    total: int = 0
    skip: int = 0
    limit: int = 50
    has_more: bool = False


class StatusResponse(BaseModel):
    """Simple status/message response."""
    status: str = "ok"
    message: Optional[str] = None
    data: Optional[Any] = None
