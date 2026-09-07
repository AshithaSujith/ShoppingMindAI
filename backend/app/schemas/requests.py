from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    session_id: str = Field(default="user1", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    history: Optional[List[Dict[str, Any]]] = None
    filters: Optional[Dict[str, List[str]]] = None

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("query must not be empty")
        return value

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, value: Optional[Dict[str, List[str]]]) -> Optional[Dict[str, List[str]]]:
        if value is None:
            return None
        if len(value) > 20:
            raise ValueError("too many filter groups")
        return {
            str(group)[:80]: [str(option)[:120] for option in options[:20]]
            for group, options in value.items()
        }


class ClearRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class ScrapeRequest(BaseModel):
    search_query: str = Field(..., min_length=1, max_length=500)
    canonical_product: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("search_query")
    @classmethod
    def normalize_search_query(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("search_query must not be empty")
        return value
