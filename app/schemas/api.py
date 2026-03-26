from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    name: str
    role: Literal["admin", "user"] = "user"


class LoginResponse(BaseModel):
    token: str
    user_id: str
    email: str
    role: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str


class DocumentOut(BaseModel):
    id: str
    owner_type: str
    owner_id: str | None
    title: str
    original_filename: str
    status: str
    source_type: str
    page_count: int | None
    created_at: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=3)
    scope_mode: Literal["global", "user", "both"] = "both"
    session_id: str | None = None


class CitationItem(BaseModel):
    document_id: str
    document_title: str
    original_filename: str
    page_start: int | None
    page_end: int | None
    chunk_id: str
    scope: str
    preview: str


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    citations: list[CitationItem]


class SessionOut(BaseModel):
    id: str
    scope_mode: str
    created_at: str


class MessageOut(BaseModel):
    role: str
    content: str
    citations_json: str | None
    created_at: str


class ReindexResponse(BaseModel):
    document_id: str
    job_id: str
    status: str


class HealthResponse(BaseModel):
    status: str
    app_name: str
