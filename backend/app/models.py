from pydantic import BaseModel
from typing import Any


class PropertyCreate(BaseModel):
    property_id: str
    name: str
    city: str | None = None
    total_rooms: int | None = None
    language: str = "en"
    custom_faqs: list[dict] = []


class Message(BaseModel):
    property_id: str
    guest_id: str
    message_id: str
    text: str


class Ask(BaseModel):
    property_id: str
    question: str


class MessageResponse(BaseModel):
    message_id: str
    intent: str | None
    confidence: float | None
    status: str
    reply: str | None = None


class AskResponse(BaseModel):
    answer: str | None
    sql: str | None = None
    rows: list[dict] = []
    source: str | None = None
    refused: bool = False
    note: str | None = None
