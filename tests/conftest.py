"""Ensure lab .env cannot poison Settings used in unit tests."""

from __future__ import annotations

import os

# Prefer loopback for any accidental get_settings() / default Settings() during imports.
os.environ["SPRUCER_HOST"] = "127.0.0.1"
os.environ.pop("SPRUCER_ALLOW_INSECURE_DEV", None)
