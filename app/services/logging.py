import json
import logging

from app.services.context import get_request_context

LOG_FORMAT_FIELDS = ["time", "level", "logger", "message", "request_id", "client_id"]


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

        payload = {
            "time": self.formatTime(record=record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id,
            "client_id": client_id,
        }

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        if "extra" in getattr(record, "extra_fields", {}):
            payload.update(getattr(record, "extra_fields", {}))

        return json.dumps(payload)


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)
