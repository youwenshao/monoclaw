"""Commercial invoice generator with multi-currency and Incoterms support."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from jinja2 import Template

logger = logging.getLogger("openclaw.trade-doc-ai.invoice")

INCOTERMS_2020 = [
    "EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP",
    "FAS", "FOB", "CFR", "CIF",
]

INVOICE_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { font-family: Arial, sans-serif; font-size: 12px; color: #1a1a1a; margin: 40px; }
  .header { display: flex; justify-content: space-between; border-bottom: 2px solid #1a365d; padding-bottom: 12px; margin-bottom: 20px; }
  .title { font-size: 22px; font-weight: bold; color: #1a365d; }
  .invoice-number { font-size: 14px; color: #4a5568; }
  .parties { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }
  .party h3 { font-size: 11px; text-transform: uppercase; color: #718096; margin-bottom: 4px; }
  .party p { margin: 2px 0; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
  th { background: #1a365d; color: white; text-align: left; padding: 8px 12px; font-size: 11px; text-transform: uppercase; }
  td { padding: 8px 12px; border-bottom: 1px solid #e2e8f0; }
  tr:nth-child(even) { background: #f7fafc; }
  .amount { text-align: right; }
  .totals { margin-left: auto; width: 300px; }
  .totals table { margin-bottom: 0; }
  .totals td { font-weight: normal; }
  .totals tr.total td { font-weight: bold; font-size: 14px; border-top: 2px solid #1a365d; }
  .footer { margin-top: 30px; padding-top: 12px; border-top: 1px solid #e2e8f0; font-size: 10px; color: #718096; }
  .terms { margin-top: 20px; }
  .terms h4 { font-size: 11px; text-transform: uppercase; color: #718096; }
</style>
</head>
<body>
<div class="header">
  <div>
    <div class="title">COMMERCIAL INVOICE</div>
    <div class="invoice-number">{{ invoice.invoice_number }}</div>
  </div>
  <div style="text-align: right;">
    <p><strong>Date:</strong> {{ invoice.invoice_date }}</p>
    <p><strong>Terms:</strong> {{ invoice.incoterms }} {{ invoice.incoterms_location }}</p>
    <p><strong>Currency:</strong> {{ invoice.currency }}</p>
  </div>
</div>

<div class="parties">
  <div class="party">
    <h3>Seller / Exporter</h3>
    <p><strong>{{ invoice.seller.name }}</strong></p>
    <p>{{ invoice.seller.address }}</p>
    {% if invoice.seller.br_number %}<p>BR: {{ invoice.seller.br_number }}</p>{% endif %}
  </div>
  <div class="party">
    <h3>Buyer / Importer</h3>
    <p><strong>{{ invoice.buyer.name }}</strong></p>
    <p>{{ invoice.buyer.address }}</p>
    {% if invoice.buyer.vat_number %}<p>VAT: {{ invoice.buyer.vat_number }}</p>{% endif %}
  </div>
</div>

<table>
  <thead>
    <tr>
      <th>#</th>
      <th>HS Code</th>
      <th>Description</th>
      <th>Qty</th>
      <th>Unit</th>
      <th class="amount">Unit Price</th>
      <th class="amount">Amount</th>
    </tr>
  </thead>
  <tbody>
    {% for item in invoice.items %}
    <tr>
      <td>{{ loop.index }}</td>
      <td>{{ item.hs_code }}</td>
      <td>{{ item.description }}</td>
      <td>{{ item.quantity }}</td>
      <td>{{ item.unit }}</td>
      <td class="amount">{{ "%.2f"|format(item.unit_price) }}</td>
      <td class="amount">{{ "%.2f"|format(item.amount) }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<div class="totals">
  <table>
    <tr><td>Subtotal</td><td class="amount">{{ invoice.currency }} {{ "%.2f"|format(invoice.subtotal) }}</td></tr>
    {% if invoice.discount %}<tr><td>Discount</td><td class="amount">-{{ invoice.currency }} {{ "%.2f"|format(invoice.discount) }}</td></tr>{% endif %}
    {% if invoice.freight %}<tr><td>Freight</td><td class="amount">{{ invoice.currency }} {{ "%.2f"|format(invoice.freight) }}</td></tr>{% endif %}
    {% if invoice.insurance %}<tr><td>Insurance</td><td class="amount">{{ invoice.currency }} {{ "%.2f"|format(invoice.insurance) }}</td></tr>{% endif %}
    <tr class="total"><td>TOTAL</td><td class="amount">{{ invoice.currency }} {{ "%.2f"|format(invoice.total) }}</td></tr>
  </table>
</div>

<div class="terms">
  <h4>Terms & Conditions</h4>
  <p>{{ invoice.terms or "Payment due within agreed terms. Goods remain property of seller until full payment." }}</p>
</div>

<div class="footer">
  <p>Country of Origin: {{ invoice.country_of_origin or "Various" }} | Transport: {{ invoice.transport_mode or "Sea" }}</p>
  <p>This invoice is computer-generated and does not require a signature.</p>
</div>
</body>
</html>
"""


class CommercialInvoiceGenerator:
    """Generate commercial invoices for international trade transactions."""

    def generate(self, invoice_data: dict) -> dict:
        """Build a structured invoice from raw data.

        Required keys in invoice_data:
          - invoice_number, invoice_date, currency
          - seller (dict: name, address)
          - buyer (dict: name, address)
          - items (list of dicts: hs_code, description, quantity, unit_price, unit)

        Optional: incoterms, freight, insurance, discount, terms.
        """
        incoterms = invoice_data.get("incoterms", "FOB")
        if incoterms not in INCOTERMS_2020:
            logger.warning("Non-standard Incoterm: %s", incoterms)

        items = [self._process_item(it) for it in invoice_data.get("items", [])]
        subtotal = sum(it["amount"] for it in items)
        discount = float(invoice_data.get("discount", 0))
        freight = float(invoice_data.get("freight", 0))
        insurance = float(invoice_data.get("insurance", 0))
        total = subtotal - discount + freight + insurance

        invoice: dict[str, Any] = {
            "invoice_number": invoice_data.get("invoice_number", ""),
            "invoice_date": invoice_data.get("invoice_date", date.today().isoformat()),
            "currency": invoice_data.get("currency", "USD"),
            "incoterms": incoterms,
            "incoterms_location": invoice_data.get("incoterms_location", ""),
            "seller": {
                "name": invoice_data.get("seller", {}).get("name", ""),
                "address": invoice_data.get("seller", {}).get("address", ""),
                "br_number": invoice_data.get("seller", {}).get("br_number", ""),
            },
            "buyer": {
                "name": invoice_data.get("buyer", {}).get("name", ""),
                "address": invoice_data.get("buyer", {}).get("address", ""),
                "vat_number": invoice_data.get("buyer", {}).get("vat_number", ""),
            },
            "items": items,
            "subtotal": subtotal,
            "discount": discount,
            "freight": freight,
            "insurance": insurance,
            "total": total,
            "country_of_origin": invoice_data.get("country_of_origin", ""),
            "transport_mode": invoice_data.get("transport_mode", "Sea"),
            "terms": invoice_data.get("terms", ""),
        }

        return invoice

    def to_html(self, invoice: dict) -> str:
        """Render the invoice dict to a printable HTML document."""
        template = Template(INVOICE_HTML_TEMPLATE)
        return template.render(invoice=invoice)

    @staticmethod
    def _process_item(item: dict) -> dict:
        qty = float(item.get("quantity", 0))
        price = float(item.get("unit_price", 0))
        return {
            "hs_code": item.get("hs_code", ""),
            "description": item.get("description", ""),
            "quantity": qty,
            "unit": item.get("unit", "pieces"),
            "unit_price": price,
            "amount": round(qty * price, 2),
        }
