from pydantic import BaseModel
from typing import Optional


class UserResponse(BaseModel):
    id: int
    telegram_id: int
    username: Optional[str] = None
    full_name: Optional[str] = None
    
    class Config:
        from_attributes = True

