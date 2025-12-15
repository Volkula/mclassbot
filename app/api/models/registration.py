from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime


class RegistrationCreate(BaseModel):
    event_id: int
    data: Dict[str, Any]


class RegistrationResponse(BaseModel):
    id: int
    event_id: int
    user_telegram_id: int
    data: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True

