import logging

import requests

from app.core.config import get_settings
from app.retriever.service import RetrievedChunk

logger = logging.getLogger(__name__)


def generate_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "Khong tim thay thong tin phu hop trong tai lieu da duoc phep truy cap."

    settings = get_settings()
    context = "\n\n".join([f"[{i+1}] {c.text}" for i, c in enumerate(chunks[:5])])
    prompt = (
        "Ban la tro ly noi bo doanh nghiep. "
        "Chi tra loi dua tren context duoc cung cap. "
        "Neu context khong du, hay noi ro khong tim thay.\n\n"
        f"Cau hoi: {question}\n\n"
        f"Context:\n{context}\n\n"
        "Tra loi ngan gon, ro rang, nghiep vu."
    )

    try:
        response = requests.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {"num_predict": 256},
            },
            timeout=settings.ollama_timeout_sec,
        )
        if response.status_code == 200:
            payload = response.json()
            text = payload.get("response", "").strip()
            if text:
                return text
            logger.warning("Ollama returned empty response")
        else:
            logger.warning("Ollama call failed: %s %s", response.status_code, response.text[:300])
    except Exception as exc:  # pragma: no cover
        logger.info("Ollama unavailable, fallback to extractive answer: %s", exc)

    bullets = [f"- {c.text[:220]}" for c in chunks[:3]]
    return "Thong tin lien quan tim thay:\n" + "\n".join(bullets)
