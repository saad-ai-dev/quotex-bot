"""Common schema types and base response models."""

from typing import Any, Generic, List, Optional, TypeVar

from bson import ObjectId
from pydantic import BaseModel, Field, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


class PyObjectId(str):
    """Custom type for MongoDB ObjectId that serializes to/from string."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_plain_validator_function(
            cls.validate,
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def validate(cls, v: Any) -> str:
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str):
            if not ObjectId.is_valid(v):
                raise ValueError(f"Invalid ObjectId: {v}")
            return v
        raise ValueError(f"Cannot convert {type(v)} to ObjectId")


class BaseResponse(BaseModel):
    """Standard API response wrapper."""

    success: bool = True
    message: str = "OK"


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response."""

    items: List[T]
    total: int
    skip: int = 0
    limit: int = 50
