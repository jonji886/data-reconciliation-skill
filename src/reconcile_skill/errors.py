"""Typed errors exposed by the reconciliation workflow."""

from __future__ import annotations


class ReconciliationError(Exception):
    """An expected, user-actionable reconciliation failure."""

    def __init__(self, code: str, message: str, *, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"{code}: {message}")


class ConfirmationRequired(ReconciliationError):
    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__("AMBIGUOUS_MAPPING", message, details=details)
