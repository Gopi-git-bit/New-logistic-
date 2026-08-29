"""Zippy Logistics — Secret Redaction for Logs.

Automatically redacts sensitive values from log output.
"""

from __future__ import annotations

import re
from typing import Any

# Patterns that indicate sensitive values
SENSITIVE_PATTERNS = [
    re.compile(r"_KEY$", re.IGNORECASE),
    re.compile(r"_SECRET$", re.IGNORECASE),
    re.compile(r"_TOKEN$", re.IGNORECASE),
    re.compile(r"_PASSWORD$", re.IGNORECASE),
    re.compile(r"AUTHORIZATION", re.IGNORECASE),
    re.compile(r"COOKIE", re.IGNORECASE),
    re.compile(r"DATABASE_URL", re.IGNORECASE),
    re.compile(r"SERVICE_ROLE", re.IGNORECASE),
    re.compile(r"API_KEY$", re.IGNORECASE),
    re.compile(r"WEBHOOK_SECRET", re.IGNORECASE),
    re.compile(r"ENCRYPTION_SECRET", re.IGNORECASE),
]

# Exact keys to redact
EXACT_SENSITIVE_KEYS = {
    "password", "secret", "token", "api_key", "apikey",
    "authorization", "cookie", "database_url",
    "supabase_service_role_key", "razorpay_key_secret",
    "razorpay_webhook_secret", "odo_api_key", "paperclip_api_key",
    "hermes_api_key", "langfuse_secret_key", "smtp_password",
}


def _is_sensitive_key(key: str) -> bool:
    """Check if a key name indicates a sensitive value."""
    key_lower = key.lower()
    if key_lower in EXACT_SENSITIVE_KEYS:
        return True
    return any(p.search(key) for p in SENSITIVE_PATTERNS)


def redact_value(value: Any) -> str:
    """Redact a sensitive value, showing only first/last chars."""
    s = str(value)
    if len(s) <= 8:
        return "***REDACTED***"
    return f"{s[:3]}...{s[-3:]}"


def redact_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact sensitive values from a dictionary."""
    result = {}
    for key, value in data.items():
        if _is_sensitive_key(key):
            result[key] = redact_value(value)
        elif isinstance(value, dict):
            result[key] = redact_dict(value)
        elif isinstance(value, list):
            result[key] = [redact_dict(v) if isinstance(v, dict) else v for v in value]
        else:
            result[key] = value
    return result


def redact_string(text: str) -> str:
    """Redact sensitive values appearing as key=value in a string."""
    result = text
    for pattern in SENSITIVE_PATTERNS:
        # Match patterns like "KEY=value" or "KEY: value"
        # Strip trailing $ anchor for the key-matching portion, but keep the rest
        raw = pattern.pattern
        key_part = raw.rstrip("$")
        matches = re.finditer(
            rf"({key_part}[=:\s]+)([^\s,;]+)",
            result,
            re.IGNORECASE,
        )
        for match in matches:
            original = match.group(0)
            key_group = match.group(1)
            val_part = match.group(2)
            redacted = f"{key_group}{redact_value(val_part)}"
            result = result.replace(original, redacted)
    return result
