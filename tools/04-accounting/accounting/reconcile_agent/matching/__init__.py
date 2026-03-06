"""Matching engine and strategies for bank-to-ledger reconciliation."""

from .engine import MatchResult, run_matching

__all__ = ["MatchResult", "run_matching"]
