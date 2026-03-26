import logging
from contextvars import ContextVar
from typing import Optional
from uuid import uuid4

request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def get_request_id() -> str:
    current = request_id_ctx.get()
    if current:
        return current
    new_id = str(uuid4())
    request_id_ctx.set(new_id)
    return new_id


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def setup_logging() -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if root_logger.handlers:
        for handler in root_logger.handlers:
            handler.addFilter(RequestIdFilter())
        return

    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.addFilter(RequestIdFilter())

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | request_id=%(request_id)s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
