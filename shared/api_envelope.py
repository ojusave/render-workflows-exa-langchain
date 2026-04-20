"""Standard JSON response shape for HTTP APIs (not used for SSE streams)."""

from typing import Any, Optional


def ok(data: Any, meta: Optional[dict] = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


def fail(
    code: str,
    message: str,
    details: Any = None,
    meta: Optional[dict] = None,
) -> dict:
    err: dict = {"code": code, "message": message}
    if details is not None:
        err["details"] = details
    return {"data": None, "error": err, "meta": meta or {}}
