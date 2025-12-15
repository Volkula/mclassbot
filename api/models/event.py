from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class EventFieldCreate(BaseModel):
    field_name: str
    field_type: str
    required: bool = False
    order: int = 0
    options: Optional[List[str]] = None


class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    date_time: datetime
    fields: List[EventFieldCreate] = []


class EventFieldResponse(BaseModel):
    id: int
    field_name: str
    field_type: str
    required: bool
    order: int
    options: Optional[List[str]] = None
    
    class Config:
        from_attributes = True


class EventResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    date_time: datetime
    status: str
    photo_file_id: Optional[str] = None
    fields: List[EventFieldResponse] = []
    
    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    events: List[EventResponse]

