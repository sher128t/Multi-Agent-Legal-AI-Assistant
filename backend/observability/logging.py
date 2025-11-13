"""Structured logging helpers for the API layer."""

from __future__ import annotations

import logging
import os
import time
import uuid
from contextlib import contextmanager
from typing import Generator

import structlog


def _configure() -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            timestamper,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


_configure()


def app_logger():
    return structlog.get_logger("app")


def audit_logger():
    return structlog.get_logger("audit")


def telemetry_logger():
    return structlog.get_logger("telemetry")


@contextmanager
def log_latency(event: str, **fields) -> Generator[str, None, None]:
    request_id = fields.get("request_id") or str(uuid.uuid4())
    start = time.perf_counter()
    try:
        yield request_id
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        fields_clean = {k: v for k, v in fields.items() if k != "request_id"}
        app_logger().info(event, request_id=request_id, latency_ms=duration_ms, **fields_clean)


def log_tokens(request_id: str, prompt_tokens: int, completion_tokens: int) -> None:
    telemetry_logger().info(
        "token_usage",
        request_id=request_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


__all__ = ["app_logger", "audit_logger", "telemetry_logger", "log_latency", "log_tokens"]

