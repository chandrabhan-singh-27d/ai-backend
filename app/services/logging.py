import json
import logging
import os
from logging.handlers import TimedRotatingFileHandler
from typing import cast

from app.services.context import get_request_context


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        request_id = "-"
        client_id = "-"

        try:
            ctx = get_request_context()
            request_id = ctx.request_id
            client_id = ctx.client_id
        except AssertionError:
            pass

        payload: dict[str, object] = {
            "time": self.formatTime(record=record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id,
            "client_id": client_id,
        }

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        extra_fields = cast("dict[str, object] | None", record.__dict__.get("extra_fields"))
        if isinstance(extra_fields, dict):
            payload.update(extra_fields)

        return json.dumps(payload)


def setup_logging(level: int = logging.INFO) -> None:
    os.makedirs("logs", exist_ok=True)

    formatter = JSONFormatter()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = TimedRotatingFileHandler(
        "logs/app.log", when="midnight", backupCount=7, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logging.basicConfig(level=level, handlers=[stream_handler, file_handler], force=True)
