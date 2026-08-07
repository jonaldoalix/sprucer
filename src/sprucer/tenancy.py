"""Vault ownership helpers.

- auth_mode=none → SHARED_OWNER (one vault for the deploy)
- any other auth → data scoped to AuthContext.subject
"""

from __future__ import annotations

import hashlib
import re

SHARED_OWNER = "shared"


def vault_owner(*, auth_mode: str, subject: str) -> str:
    mode = (auth_mode or "").strip().lower()
    if mode == "none":
        return SHARED_OWNER
    sub = (subject or "").strip()
    return sub or SHARED_OWNER


def owner_key(owner: str) -> str:
    """Short stable prefix for globally unique application ids."""
    raw = (owner or SHARED_OWNER).strip() or SHARED_OWNER
    if raw == SHARED_OWNER:
        return "shared"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    slug = re.sub(r"[^a-zA-Z0-9]+", "", raw.lower())[:8] or "user"
    return f"{slug}-{digest}"


def api_key_subject(api_key: str) -> str:
    digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
    return f"api-key:{digest}"
