"""Jinja2-based HTML invoice renderer."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "data" / "invoice_templates"


class InvoiceTemplateEngine:

    def __init__(self) -> None:
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html"]),
        )
        self.env.filters["currency_fmt"] = self._currency_fmt

    @staticmethod
    def _currency_fmt(value: float, symbol: str = "") -> str:
        """Format a number with commas and 2 decimal places."""
        formatted = f"{value:,.2f}"
        return f"{symbol}{formatted}" if symbol else formatted

    def render_invoice_html(
        self,
        invoice: dict,
        items: list[dict],
        company: dict,
        bank_accounts: list[dict],
    ) -> str:
        """Render a professional HTML invoice from the standard template."""
        template = self.env.get_template("standard.html")
        return template.render(
            invoice=invoice,
            items=items,
            company=company,
            bank_accounts=bank_accounts,
        )
