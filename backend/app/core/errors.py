"""API error types with user-friendly messaging."""
from typing import Any, Dict, Optional

from fastapi import HTTPException


class NagrikError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str, detail: Optional[str] = None, hint: Optional[str] = None):
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.hint = hint
        self.payload: Dict[str, Any] = {
            "code": code,
            "message": message,
            "detail": detail,
            "hint": hint,
        }


class ConfigurationError(NagrikError):
    """A provider/API key/tool is missing — surfaced prominently in the UI."""

    def __init__(self, what: str, hint: str):
        super().__init__(
            status_code=503,
            code="configuration",
            message=f"{what} is not configured.",
            hint=hint,
        )
