"""Base statement parser interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class Transaction:
    transaction_date: date
    value_date: date | None
    description: str
    reference: str | None
    debit: float
    credit: float
    balance: float | None
    currency: str
    transaction_type: str | None


@dataclass
class ParseResult:
    transactions: list[Transaction]
    bank_name: str
    account_number: str | None = None
    currency: str = "HKD"
    statement_date: date | None = None
    opening_balance: float | None = None
    closing_balance: float | None = None
    warnings: list[str] = field(default_factory=list)


class BaseStatementParser(ABC):
    bank_name: str

    @abstractmethod
    def parse(self, file_path: Path) -> ParseResult:
        """Parse a bank statement file and return structured transactions."""
        ...

    @abstractmethod
    def detect(self, file_path: Path) -> bool:
        """Return True if this parser can handle the given file."""
        ...


PARSER_REGISTRY: list[type[BaseStatementParser]] = []


def register_parser(cls: type[BaseStatementParser]) -> type[BaseStatementParser]:
    """Class decorator to auto-register a parser."""
    PARSER_REGISTRY.append(cls)
    return cls


def detect_parser(file_path: Path) -> BaseStatementParser | None:
    """Try each registered parser's detect() and return the first match."""
    for parser_cls in PARSER_REGISTRY:
        parser = parser_cls()
        try:
            if parser.detect(file_path):
                return parser
        except Exception:
            continue
    return None
