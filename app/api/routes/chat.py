import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import enforce_rate_limit
from app.db.session import get_db
from app.llm.service import generate_answer
from app.models.chat import ChatMessage, ChatSession, MessageRole, ScopeMode
from app.models.user import User
from app.retriever.service import retrieve_chunks
from app.schemas.api import ChatRequest, ChatResponse, MessageOut, SessionOut
from app.services.audit import write_audit_log
from app.services.citation import build_citations

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, current_user: User = Depends(enforce_rate_limit), db: Session = Depends(get_db)) -> ChatResponse:
    session = None
    if payload.session_id:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == payload.session_id, ChatSession.user_id == current_user.id)
            .first()
        )

    if not session:
        session = ChatSession(user_id=current_user.id, scope_mode=ScopeMode(payload.scope_mode))
        db.add(session)
        db.commit()
        db.refresh(session)

    db.add(ChatMessage(session_id=session.id, role=MessageRole.user, content=payload.question))
    db.commit()

    chunks = retrieve_chunks(db, question=payload.question, user=current_user, scope_mode=payload.scope_mode)
    answer = generate_answer(payload.question, chunks)
    citations = build_citations(payload.question, answer, chunks)

    db.add(
        ChatMessage(
            session_id=session.id,
            role=MessageRole.assistant,
            content=answer,
            citations_json=json.dumps(citations, ensure_ascii=True),
        )
    )
    db.commit()

    write_audit_log(
        db,
        actor_id=current_user.id,
        action="chat.ask",
        resource_type="chat_session",
        resource_id=session.id,
        metadata={"scope_mode": payload.scope_mode, "citations": len(citations)},
    )

    return ChatResponse(session_id=session.id, answer=answer, citations=citations)


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(current_user: User = Depends(enforce_rate_limit), db: Session = Depends(get_db)) -> list[SessionOut]:
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.created_at.desc())
        .all()
    )
    return [SessionOut(id=s.id, scope_mode=s.scope_mode.value, created_at=s.created_at.isoformat()) for s in sessions]


@router.get("/sessions/{session_id}", response_model=list[MessageOut])
def get_session_messages(session_id: str, current_user: User = Depends(enforce_rate_limit), db: Session = Depends(get_db)) -> list[MessageOut]:
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        return []
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return [
        MessageOut(
            role=m.role.value,
            content=m.content,
            citations_json=m.citations_json,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]
