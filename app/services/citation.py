import re

from app.retriever.service import RetrievedChunk

WORD_RE = re.compile(r"\w+", flags=re.UNICODE)
STOPWORDS = {
    "la", "va", "cua", "cho", "voi", "tren", "duoc", "trong", "khi", "neu", "thi", "mot", "nhung", "cac",
    "the", "nay", "do", "de", "tu", "tai", "theo", "or", "and", "the", "a", "an", "is", "are", "of", "to",
}


def _tokenize(text: str) -> set[str]:
    tokens = {t.lower() for t in WORD_RE.findall(text)}
    return {t for t in tokens if len(t) >= 2 and t not in STOPWORDS}


def _overlap(anchor: str, text: str) -> float:
    a = _tokenize(anchor)
    b = _tokenize(text)
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a))


def build_citations(question: str, answer: str, chunks: list[RetrievedChunk], max_items: int = 4) -> list[dict]:
    if not chunks:
        return []

    scored: list[tuple[float, float, RetrievedChunk]] = []
    for c in chunks:
        q_overlap = _overlap(question, c.text)
        a_overlap = _overlap(answer, c.text)
        semantic = max(0.0, min(1.0, (c.score + 1.0) / 2.0))
        final = 0.60 * q_overlap + 0.20 * a_overlap + 0.20 * semantic
        scored.append((final, q_overlap, c))

    scored.sort(key=lambda x: x[0], reverse=True)

    output: list[dict] = []
    seen_keys: set[tuple[str, int | None, int | None]] = set()
    per_document_count: dict[str, int] = {}

    for relevance, q_overlap, c in scored:
        key = (c.document_id, c.page_start, c.page_end)
        if key in seen_keys:
            continue
        if per_document_count.get(c.document_id, 0) >= 2:
            continue
        if output and q_overlap < 0.08:
            continue
        if relevance < 0.08 and output:
            continue

        output.append(
            {
                "document_id": c.document_id,
                "document_title": c.document_title,
                "original_filename": c.original_filename,
                "page_start": c.page_start,
                "page_end": c.page_end,
                "chunk_id": c.chunk_id,
                "scope": c.scope,
                "preview": c.text[:200],
            }
        )
        seen_keys.add(key)
        per_document_count[c.document_id] = per_document_count.get(c.document_id, 0) + 1
        if len(output) >= max_items:
            break

    if not output and chunks:
        c = chunks[0]
        output.append(
            {
                "document_id": c.document_id,
                "document_title": c.document_title,
                "original_filename": c.original_filename,
                "page_start": c.page_start,
                "page_end": c.page_end,
                "chunk_id": c.chunk_id,
                "scope": c.scope,
                "preview": c.text[:200],
            }
        )

    return output
