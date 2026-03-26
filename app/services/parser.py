import re
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader


class ParsedChunk:
    def __init__(self, text: str, page_start: int | None, page_end: int | None) -> None:
        self.text = text
        self.page_start = page_start
        self.page_end = page_end


HEADER_PATTERNS = [
    re.compile(r"^quy\s*che\s*quan\s*tri\s*noi\s*bo", re.IGNORECASE),
    re.compile(r"^sua\s*doi\s*lan\s*thu", re.IGNORECASE),
    re.compile(r"^page\s+\d+$", re.IGNORECASE),
]


def parse_document(file_path: Path) -> tuple[list[ParsedChunk], int | None]:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(file_path)
    if suffix == ".txt":
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        return [ParsedChunk(text=text, page_start=None, page_end=None)], None
    if suffix == ".docx":
        doc = DocxDocument(str(file_path))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return [ParsedChunk(text=text, page_start=None, page_end=None)], None
    if suffix in {".csv", ".xlsx"}:
        text = file_path.read_text(encoding="utf-8", errors="ignore") if suffix == ".csv" else ""
        return [ParsedChunk(text=text, page_start=None, page_end=None)], None
    raise ValueError(f"Unsupported suffix: {suffix}")


def parse_pdf(file_path: Path) -> tuple[list[ParsedChunk], int | None]:
    reader = PdfReader(str(file_path))
    parsed: list[ParsedChunk] = []
    for idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        clean = normalize_text(text)
        if clean.strip():
            parsed.append(ParsedChunk(text=clean, page_start=idx, page_end=idx))
    return parsed, len(reader.pages)


def normalize_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    filtered: list[str] = []
    for line in lines:
        if not line:
            continue
        if _is_noise_line(line):
            continue
        filtered.append(line)
    return "\n".join(filtered)


def _is_noise_line(line: str) -> bool:
    if len(line) <= 2:
        return True

    normalized = _normalize_for_match(line)
    for pattern in HEADER_PATTERNS:
        if pattern.match(normalized):
            return True

    return False


def _normalize_for_match(line: str) -> str:
    # Strip Vietnamese accents for robust matching in noisy PDFs.
    mapping = str.maketrans(
        "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ",
        "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd",
    )
    return line.lower().translate(mapping)
