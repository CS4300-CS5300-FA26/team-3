"""Redact account credentials where Django and Mangum emit request logs."""
from copy import copy
import logging
import re

from django.http import HttpRequest


# Also match standalone signed values, such as resolver kwargs or a Referer URL.
_TOKEN = re.compile(r"\.?[A-Za-z0-9_-]+:[A-Za-z0-9]+:[A-Za-z0-9_-]{43}")
# Django default_token_generator: base36 timestamp and truncated SHA-256 HMAC.
_RESET_TOKEN = re.compile(r"\b[0-9a-z]+-[0-9a-f]{32}\b")
_VERIFY_PATH = re.compile(r"(/accounts/verify/)[^/?\s]+")
_PERCENT_ESCAPE = re.compile(r"%([0-9a-fA-F]{2})")


def redact(value):
    """Copy ordinary log containers, leaving arbitrary application objects alone."""
    if isinstance(value, str):
        # Access logs retain URL escapes. Decode printable ASCII for matching,
        # but preserve encoded controls so redaction cannot introduce log lines.
        decoded = _PERCENT_ESCAPE.sub(
            lambda match: chr(int(match[1], 16))
            if 32 <= int(match[1], 16) < 127 else match[0], value,
        )
        safe = _TOKEN.sub("[redacted]", _VERIFY_PATH.sub(r"\1[redacted]", decoded))
        safe = _RESET_TOKEN.sub("[redacted]", safe)
        return safe if safe != decoded else value
    if isinstance(value, bytes):
        return redact(value.decode("utf-8", errors="replace")).encode("utf-8")
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return type(value)(redact(item) for item in value)
    return value


class VerificationTokenFilter(logging.Filter):
    def filter(self, record):
        # Freeze the formatted message too: args can contain request-like objects.
        message = redact(record.getMessage())
        for key, value in list(vars(record).items()):
            setattr(record, key, redact(value))
        record.msg, record.args = message, ()
        request = getattr(record, "request", None)
        if isinstance(request, HttpRequest):
            # Logging must never alter the request used by routing, CSRF or views.
            safe = copy(request)
            safe.path, safe.path_info = redact(request.path), redact(request.path_info)
            safe.META = redact(request.META)
            if hasattr(request, "environ"):
                safe.environ = safe.META
            if hasattr(request, "scope"):
                safe.scope = redact(request.scope)
            if request.resolver_match is not None:
                # ResolverMatch forbids copy/pickle; copy its diagnostic attributes.
                match = request.resolver_match
                safe.resolver_match = object.__new__(type(match))
                safe.resolver_match.__dict__ = redact(vars(match))
            record.request = safe
        if record.exc_info:
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return True
