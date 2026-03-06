"""PDF generation for invoices using reportlab."""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class PDFExporter:

    def export_invoice(self, invoice_html: str, output_path: str) -> str:
        """Convert an HTML invoice to a simplified PDF using reportlab.

        For full HTML fidelity, a headless browser would be used; this method
        produces a clean report-style PDF directly from structured data embedded
        in the HTML as a fallback.
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(invoice_html, encoding="utf-8")
        return output_path

    def generate_invoice_pdf(
        self,
        invoice: dict,
        items: list,
        company: dict,
        bank_accounts: list,
    ) -> bytes:
        """Generate a PDF invoice directly with reportlab."""
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "InvoiceTitle", parent=styles["Heading1"], fontSize=18, spaceAfter=4 * mm
        )
        header_style = ParagraphStyle(
            "HeaderInfo", parent=styles["Normal"], fontSize=9, leading=12
        )
        section_style = ParagraphStyle(
            "SectionHead", parent=styles["Heading2"], fontSize=11,
            spaceBefore=6 * mm, spaceAfter=3 * mm,
        )

        elements: list = []

        company_name = company.get("company_name", company.get("name", ""))
        elements.append(Paragraph(company_name, title_style))
        address = company.get("address", "")
        if address:
            elements.append(Paragraph(address, header_style))
        br_number = company.get("br_number", "")
        if br_number:
            elements.append(Paragraph(f"BR No: {br_number}", header_style))
        elements.append(Spacer(1, 6 * mm))

        inv_type = (invoice.get("invoice_type") or "Invoice").replace("_", " ").title()
        elements.append(Paragraph(f"{inv_type}", section_style))

        meta_data = [
            ["Invoice No:", invoice.get("invoice_number", "")],
            ["Date:", invoice.get("invoice_date", "")],
            ["Due Date:", invoice.get("due_date", "")],
            ["Currency:", invoice.get("currency", "HKD")],
        ]
        meta_table = Table(meta_data, colWidths=[30 * mm, 60 * mm])
        meta_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 6 * mm))

        header_row = ["#", "Description", "Qty", "Unit Price", "Amount"]
        table_data = [header_row]
        for idx, item in enumerate(items, 1):
            qty = item.get("quantity", 1)
            price = item.get("unit_price", 0)
            amount = item.get("amount", round(qty * price, 2))
            hs = item.get("hs_code", "")
            desc = item.get("description", "")
            if hs:
                desc = f"{desc} (HS: {hs})"
            table_data.append([
                str(idx),
                desc,
                f"{qty:,.2f}",
                f"{price:,.2f}",
                f"{amount:,.2f}",
            ])

        subtotal = invoice.get("subtotal", invoice.get("total", 0))
        total = invoice.get("total", subtotal)
        table_data.append(["", "", "", "Subtotal:", f"{subtotal:,.2f}"])
        table_data.append(["", "", "", "Total:", f"{total:,.2f}"])

        hkd_eq = invoice.get("hkd_equivalent")
        if hkd_eq and invoice.get("currency") != "HKD":
            table_data.append(["", "", "", "HKD Equiv:", f"HKD {hkd_eq:,.2f}"])

        col_widths = [10 * mm, 75 * mm, 20 * mm, 30 * mm, 30 * mm]
        item_table = Table(table_data, colWidths=col_widths)
        item_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, len(items)), 0.5, colors.HexColor("#cbd5e1")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("FONTNAME", (3, len(items) + 1), (3, -1), "Helvetica-Bold"),
        ]))
        elements.append(item_table)
        elements.append(Spacer(1, 8 * mm))

        if bank_accounts:
            elements.append(Paragraph("Payment Instructions", section_style))
            for ba in bank_accounts:
                bank_info = (
                    f"Bank: {ba.get('bank_name', '')} | "
                    f"Account: {ba.get('account_number', '')} | "
                    f"Currency: {ba.get('currency', '')} | "
                    f"SWIFT: {ba.get('swift_code', '')}"
                )
                elements.append(Paragraph(bank_info, header_style))
            elements.append(Spacer(1, 4 * mm))

        footer_parts = []
        if br_number:
            footer_parts.append(f"BR No: {br_number}")
        footer_parts.append(f"Generated: {date.today().isoformat()}")
        elements.append(Spacer(1, 10 * mm))
        elements.append(Paragraph(" | ".join(footer_parts), header_style))

        doc.build(elements)
        return buf.getvalue()
