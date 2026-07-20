from pydantic import BaseModel
from typing import List, Optional

class SearchRequest(BaseModel):
    query: str
    session_id: str = "user1"
    history: Optional[List[dict]] = None


class ClearRequest(BaseModel):
    session_id: str


class ScrapeRequest(BaseModel):
    search_query: str
    canonical_product: dict