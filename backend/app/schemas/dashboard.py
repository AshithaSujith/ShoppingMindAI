from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class WishlistRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    product: Dict[str, Any]


class PriceAlertRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    search_query: str = Field(..., min_length=1, max_length=500)
    target_price: Optional[float] = Field(default=None, gt=0, le=100000000)
