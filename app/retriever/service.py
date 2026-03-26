import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus, OwnerType
from app.models.user import User
from app.services.embedding import embedding_service
from app.services.vector_store import vector_store

WORD_RE = re.compile(r"\w+", flags=re.UNICODE)
STOPWORDS = {
    "la", "va", "cua", "cho", "voi", "tren", "duoc", "trong", "khi", "neu", "thi", "mot", "nhung", "cac",
    "the", "nay", "do", "de", "tu", "tai", "theo", "or", "and", "the", "a", "an", "is", "are", "of", "to",
}


@dataclass
class RetrievedChunk:
    score: float
    chunk_id: str
    document_id: str
    document_title: str
    original_filename: str
    page_start: int | None
    page_end: int | None
    scope: str
    text: str


@dataclass
class RankedCandidate:
    chunk: RetrievedChunk
    combined_score: float
    lexical_score: float


def _tokenize(text: str) -> set[str]:
    tokens = {t.lower() for t in WORD_RE.findall(text)}
    return {t for t in tokens if len(t) >= 2 and t not in STOPWORDS}


def _lexical_overlap(query: str, text: str) -> float:
    q_tokens = _tokenize(query)
    if not q_tokens:
        return 0.0
    c_tokens = _tokenize(text)
    if not c_tokens:
        return 0.0
    return len(q_tokens & c_tokens) / max(1, len(q_tokens))


def _normalize_vector_score(score: float) -> float:
    return max(0.0, min(1.0, (score + 1.0) / 2.0))


def _allowed_document_ids(db: Session, user: User, scope_mode: str) -> set[str]:
    query = db.query(Document).filter(Document.status == DocumentStatus.indexed)

    if scope_mode == "global":
        docs = query.filter(Document.owner_type == OwnerType.global_).all()
    elif scope_mode == "user":
        docs = query.filter(Document.owner_type == OwnerType.user, Document.owner_id == user.id).all()
    else:
        docs = query.filter(
            (Document.owner_type == OwnerType.global_)
            | ((Document.owner_type == OwnerType.user) & (Document.owner_id == user.id))
        ).all()
    return {d.id for d in docs}


def is_metadata_allowed(meta: dict, user_id: str, scope_mode: str, allowed_docs: set[str]) -> bool:
    if meta.get("document_id") not in allowed_docs:
        return False
    if scope_mode == "global":
        return meta.get("owner_type") == "global"
    if scope_mode == "user":
        return meta.get("owner_type") == "user" and meta.get("owner_id") == user_id
    return (meta.get("owner_type") == "global") or (
        meta.get("owner_type") == "user" and meta.get("owner_id") == user_id
    )


def _from_meta(meta: dict, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        score=float(score),
        chunk_id=meta["chunk_id"],
        document_id=meta["document_id"],
        document_title=meta["document_title"],
        original_filename=meta["original_filename"],
        page_start=meta.get("page_start"),
        page_end=meta.get("page_end"),
        scope="Company KB" if meta.get("owner_type") == "global" else "My Documents",
        text=meta.get("text", ""),
    )


def rank_candidates(question: str, candidates: list[RetrievedChunk]) -> list[RankedCandidate]:
    ranked: list[RankedCandidate] = []
    for c in candidates:
        lexical = _lexical_overlap(question, c.text)
        vector_norm = _normalize_vector_score(c.score)
        combined = 0.55 * vector_norm + 0.45 * lexical
        ranked.append(RankedCandidate(chunk=c, combined_score=combined, lexical_score=lexical))

    ranked.sort(key=lambda x: x.combined_score, reverse=True)
    return ranked


def _collect_hybrid_candidates(question: str, raw_semantic: list[dict], filtered_meta: list[dict]) -> list[RetrievedChunk]:
    by_chunk: dict[str, RetrievedChunk] = {}

    for item in raw_semantic:
        meta = item["metadata"]
        chunk = _from_meta(meta, item["score"])
        by_chunk[chunk.chunk_id] = chunk

    lexical_ranked: list[tuple[float, dict]] = []
    for meta in filtered_meta:
        lex = _lexical_overlap(question, meta.get("text", ""))
        if lex <= 0:
            continue
        lexical_ranked.append((lex, meta))

    lexical_ranked.sort(key=lambda x: x[0], reverse=True)
    for lex, meta in lexical_ranked[:18]:
        pseudo_semantic = max(-1.0, min(1.0, 2 * lex - 1))
        chunk = _from_meta(meta, pseudo_semantic)
        existing = by_chunk.get(chunk.chunk_id)
        if not existing or chunk.score > existing.score:
            by_chunk[chunk.chunk_id] = chunk

    return list(by_chunk.values())


def retrieve_chunks(
    db: Session,
    *,
    question: str,
    user: User,
    scope_mode: str,
    top_k: int = 6,
    min_score: float = 0.05,
) -> list[RetrievedChunk]:
    allowed_docs = _allowed_document_ids(db, user, scope_mode)
    if not allowed_docs:
        return []

    q_vec = embedding_service.embed_query(question)

    def filter_fn(meta: dict) -> bool:
        return is_metadata_allowed(meta, user.id, scope_mode, allowed_docs)

    raw_semantic = vector_store.search(q_vec, top_k=max(top_k * 4, 12), filter_fn=filter_fn)
    filtered_meta = vector_store.filtered_metadata(filter_fn)
    all_candidates = _collect_hybrid_candidates(question, raw_semantic, filtered_meta)

    # Keep base min_score only for truly semantic results; lexical results can still pass by overlap.
    filtered = [c for c in all_candidates if c.score >= min_score or _lexical_overlap(question, c.text) >= 0.06]
    ranked = rank_candidates(question, filtered)

    selected: list[RetrievedChunk] = []
    seen_chunk_ids: set[str] = set()
    for item in ranked:
        c = item.chunk
        if c.chunk_id in seen_chunk_ids:
            continue
        if item.lexical_score < 0.02 and _normalize_vector_score(c.score) < 0.56:
            continue
        selected.append(c)
        seen_chunk_ids.add(c.chunk_id)
        if len(selected) >= top_k:
            break

    return selected
