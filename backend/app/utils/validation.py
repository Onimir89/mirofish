"""Shared validation helpers for API blueprints."""

import re


def validate_id(id_str: str) -> bool:
    """Check that an ID is safe for use in file paths (hex + dashes, 6-36 chars)."""
    return bool(re.fullmatch(r'[a-f0-9\-]{6,36}', id_str))
