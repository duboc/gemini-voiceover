"""Tests for the review-step timeout.

Cloud Run kills the inbound request at its --timeout (max 3600s), but the
review loop in process_video used to spin for up to 1 hour with the value
hardcoded. Even if Cloud Run is now bumped to the 3600s ceiling, a shorter
default (30 minutes) bounds 'forgotten' jobs that hold a worker thread.

REVIEW_TIMEOUT_SEC is read from Config so operators can tune per-deployment.
"""
from __future__ import annotations

import pytest


def test_config_exposes_review_timeout_with_30min_default():
    from config import Config

    assert hasattr(Config, "REVIEW_TIMEOUT_SEC")
    # 30 minutes default is the new bound
    assert Config.REVIEW_TIMEOUT_SEC == 1800


def test_review_timeout_is_int_and_positive():
    from config import Config

    assert isinstance(Config.REVIEW_TIMEOUT_SEC, int)
    assert Config.REVIEW_TIMEOUT_SEC > 0


def test_app_uses_config_review_timeout_not_hardcoded():
    """The string 'max_wait_time = 3600' (or any literal != Config) must be
    gone from app.py — it should reference Config.REVIEW_TIMEOUT_SEC."""
    import inspect
    import app as app_module

    source = inspect.getsource(app_module)
    assert "Config.REVIEW_TIMEOUT_SEC" in source, (
        "app.py must reference Config.REVIEW_TIMEOUT_SEC for the review wait loop"
    )
    # Guard against the old hardcoded literal sneaking back in
    assert "max_wait_time = 3600" not in source, (
        "Remove the legacy hardcoded `max_wait_time = 3600` in app.py"
    )
