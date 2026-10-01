import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Context variable to hold request correlation ID across async handlers
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class StructuredJsonFormatter(logging.Formatter):
    """Formats Python log records into production-safe structured JSON."""

    # Sensitive keys that must never be emitted into structured logs
    SENSITIVE_KEYS = {
        "password",
        "admin_key",
        "api_key",
        "authorization",
        "token",
        "secret",
        "database_url",
    }

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Inject request_id from record or context variable
        req_id = getattr(record, "request_id", None) or request_id_ctx.get()
        if req_id:
            log_obj["request_id"] = req_id

        # Attach request metrics or context data if present
        for key in ("method", "path", "status_code", "duration_ms", "client_ip"):
            if hasattr(record, key):
                log_obj[key] = getattr(record, key)

        # Sanitize any extra dict attributes
        extra_data = getattr(record, "extra_data", None)
        if isinstance(extra_data, dict):
            sanitized = {}
            for k, v in extra_data.items():
                if any(s in k.lower() for s in self.SENSITIVE_KEYS):
                    sanitized[k] = "[REDACTED]"
                else:
                    sanitized[k] = v
            log_obj["extra"] = sanitized

        # Inspect and redact any custom direct attributes on record
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message", "asctime", "request_id",
            "method", "path", "status_code", "duration_ms", "client_ip", "extra_data"
        }
        for k, v in record.__dict__.items():
            if k not in standard_attrs and not k.startswith("_"):
                if any(s in k.lower() for s in self.SENSITIVE_KEYS):
                    log_obj[k] = "[REDACTED]"
                else:
                    log_obj[k] = v

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def configure_logging(log_level: str = "INFO") -> None:
    """Configures root and application loggers to output structured JSON."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Check if a StructuredJsonFormatter is already configured
    has_json_handler = any(
        isinstance(h, logging.StreamHandler) and isinstance(h.formatter, StructuredJsonFormatter)
        for h in root_logger.handlers
    )

    if not has_json_handler:
        for h in list(root_logger.handlers):
            root_logger.removeHandler(h)

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJsonFormatter())
        root_logger.addHandler(handler)

    # Set backend application logger level
    app_logger = logging.getLogger("backend.app")
    app_logger.setLevel(level)
