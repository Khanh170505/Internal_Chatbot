from dataclasses import dataclass

from app.services.parser import ParsedChunk


@dataclass
class ChunkItem:
    chunk_index: int
    text: str
    page_start: int | None
    page_end: int | None
    token_count: int


def split_into_chunks(parsed_chunks: list[ParsedChunk], chunk_size: int = 220, overlap: int = 40) -> list[ChunkItem]:
    items: list[ChunkItem] = []
    idx = 0

    for source in parsed_chunks:
        words = source.text.split()
        if not words:
            continue

        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            segment = words[start:end]
            text = " ".join(segment).strip()
            if text:
                items.append(
                    ChunkItem(
                        chunk_index=idx,
                        text=text,
                        page_start=source.page_start,
                        page_end=source.page_end,
                        token_count=len(segment),
                    )
                )
                idx += 1

            if end >= len(words):
                break
            start = max(0, end - overlap)

    return items
