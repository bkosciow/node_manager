"""Unit tests for the Apprise notification service."""

import logging

from app.config import settings
from app.services.apprise import Apprise, ErrorHandler


class TestErrorHandler:
    def test_init_succeeds(self):
        h = ErrorHandler()
        assert isinstance(h, logging.Handler)

    def test_init_sets_error_level(self):
        h = ErrorHandler()
        assert h.level == logging.ERROR


class TestApprise:
    def test_info_is_noop_without_url(self, monkeypatch):
        monkeypatch.setattr(settings, "apprise_url", "")
        Apprise().info("message")
