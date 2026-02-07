from __future__ import annotations

from datetime import datetime
from pathlib import Path

try:
    from fpdf import FPDF  # type: ignore
except Exception:  # pragma: no cover
    FPDF = None  # type: ignore


class InvoiceGenerator:
    def __init__(self, store_name: str = "Grocery Mart"):
        self.store_name = store_name

    def _safe_text(self, value: object) -> str:
        """
        FPDF built-in fonts are not Unicode. Sanitize strings to be Latin-1 safe.
        This prevents runtime errors when input contains symbols like ₹ or →.
        """
        s = "" if value is None else str(value)
        s = (
            s.replace("₹", "Rs.")
            .replace("•", "-")
            .replace("—", "-")
            .replace("–", "-")
            .replace("→", "->")
            .replace("…", "...")
        )
        try:
            return s.encode("latin-1", errors="replace").decode("latin-1")
        except Exception:
            return "".join(ch if ord(ch) < 128 else "?" for ch in s)

    def generate_invoice(
        self,
        filepath: str,
        product: str | None = None,
        qty: int | None = None,
        unit_price: float | None = None,
        total: float | None = None,
        buyer_name: str = "",
        buyer_mobile: str = "",
        items: list[dict[str, object]] | None = None,
        invoice_no: str | None = None,
    ):
        if FPDF is None:
            raise RuntimeError("Missing dependency: fpdf2. Install with `pip install -r requirements.txt`.")

        now = datetime.now()
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=16)

        # Page frame
        pdf.set_draw_color(210, 210, 210)
        pdf.rect(8, 8, 194, 281)

        if invoice_no is None:
            try:
                stem = Path(filepath).stem
                # Common pattern: Invoice_<id>_<timestamp>.pdf
                if stem.lower().startswith("invoice_"):
                    parts = stem.split("_")
                    if len(parts) >= 2 and parts[1].isdigit():
                        invoice_no = parts[1]
            except Exception:
                invoice_no = None

        pdf.set_text_color(33, 37, 41)
        pdf.set_font("Arial", "B", 20)
        pdf.cell(0, 10, self._safe_text(self.store_name), ln=True, align="C")
        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(0, 6, self._safe_text("Fresh groceries - Daily essentials"), ln=True, align="C")
        pdf.set_draw_color(180, 180, 180)
        pdf.line(20, pdf.get_y() + 2, 190, pdf.get_y() + 2)
        pdf.ln(8)

        # Header row: invoice meta
        pdf.set_text_color(33, 37, 41)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 7, self._safe_text("Invoice Receipt"), ln=True, align="L")
        pdf.set_font("Arial", "", 10)
        if invoice_no:
            pdf.cell(0, 6, self._safe_text(f"Invoice No: {invoice_no}"), ln=True, align="L")
        pdf.cell(
            0,
            6,
            self._safe_text(f"Date: {now.strftime('%A, %d %B %Y')}   Time: {now.strftime('%H:%M:%S')}"),
            ln=True,
            align="L",
        )
        pdf.ln(4)

        # Customer box
        pdf.set_fill_color(245, 246, 248)
        pdf.set_draw_color(220, 220, 220)
        box_x = 12
        box_w = 186
        box_h = 22
        y0 = pdf.get_y()
        pdf.rect(box_x, y0, box_w, box_h, style="DF")
        pdf.set_xy(box_x + 4, y0 + 4)
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(33, 37, 41)
        pdf.cell(0, 6, self._safe_text("Customer Details"), ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(60, 60, 60)
        pdf.set_x(box_x + 4)
        pdf.cell(90, 6, self._safe_text(f"Name: {buyer_name or 'N/A'}"))
        pdf.cell(0, 6, self._safe_text(f"Mobile: {buyer_mobile or 'N/A'}"), ln=True)
        pdf.ln(8)

        pdf.set_font("Arial", "B", 12)
        pdf.set_fill_color(230, 230, 230)
        pdf.set_text_color(33, 37, 41)
        pdf.cell(0, 8, self._safe_text("Sale Details"), ln=True, fill=True)

        pdf.set_font("Arial", "", 12)
        if items:
            # More columns, smaller font.
            pdf.set_font("Arial", "", 10)
            col_w = (70, 15, 25, 15, 15, 40)  # total 180
            pdf.set_fill_color(248, 249, 250)
            pdf.set_draw_color(200, 200, 200)
            pdf.cell(col_w[0], 8, self._safe_text("Product"), 1, 0, "L", True)
            pdf.cell(col_w[1], 8, self._safe_text("Qty"), 1, 0, "C", True)
            pdf.cell(col_w[2], 8, self._safe_text("Unit"), 1, 0, "R", True)
            pdf.cell(col_w[3], 8, self._safe_text("GST%"), 1, 0, "C", True)
            pdf.cell(col_w[4], 8, self._safe_text("Tax%"), 1, 0, "C", True)
            pdf.cell(col_w[5], 8, self._safe_text("Total"), 1, 0, "R", True)
            pdf.ln()

            computed_subtotal = 0.0
            computed_tax = 0.0
            computed_total = 0.0
            zebra = False
            for item in items:
                p = str(item.get("product", ""))
                q = int(item.get("qty", 0) or 0)
                up = item.get("unit_price", None)
                try:
                    up_f = float(up) if up is not None else None
                except Exception:
                    up_f = None
                gst_p = item.get("gst_percent", 0) or 0
                tax_p = item.get("tax_percent", 0) or 0
                try:
                    gst_f = float(gst_p)
                except Exception:
                    gst_f = 0.0
                try:
                    tax_f = float(tax_p)
                except Exception:
                    tax_f = 0.0

                subtotal_v = item.get("subtotal", None)
                try:
                    sub_f = float(subtotal_v) if subtotal_v is not None else (q * up_f if up_f is not None else 0.0)
                except Exception:
                    sub_f = 0.0

                tax_amount_v = item.get("tax_amount", None)
                try:
                    tax_amt_f = (
                        float(tax_amount_v)
                        if tax_amount_v is not None
                        else (sub_f * (gst_f + tax_f) / 100.0)
                    )
                except Exception:
                    tax_amt_f = 0.0

                line_total = item.get("total", None)
                try:
                    lt_f = float(line_total) if line_total is not None else (sub_f + tax_amt_f)
                except Exception:
                    lt_f = sub_f + tax_amt_f

                computed_subtotal += sub_f
                computed_tax += tax_amt_f
                computed_total += lt_f

                zebra = not zebra
                if zebra:
                    pdf.set_fill_color(255, 255, 255)
                else:
                    pdf.set_fill_color(248, 248, 248)
                pdf.cell(col_w[0], 8, self._safe_text(p[:36]), 1, 0, "L", True)
                pdf.cell(col_w[1], 8, self._safe_text(str(q)), 1, 0, "C", True)
                pdf.cell(
                    col_w[2],
                    8,
                    self._safe_text(f"{up_f:.2f}" if up_f is not None else "N/A"),
                    1,
                    0,
                    "R",
                    True,
                )
                pdf.cell(col_w[3], 8, self._safe_text(f"{gst_f:g}"), 1, 0, "C", True)
                pdf.cell(col_w[4], 8, self._safe_text(f"{tax_f:g}"), 1, 0, "C", True)
                pdf.cell(col_w[5], 8, self._safe_text(f"{lt_f:.2f}"), 1, 0, "R", True)
                pdf.ln()

            if total is None:
                total = computed_total

            pdf.ln(3)
            pdf.set_font("Arial", "B", 11)
            pdf.set_text_color(33, 37, 41)
            pdf.cell(180, 7, self._safe_text(f"Subtotal: {computed_subtotal:.2f}"), ln=True, align="R")
            pdf.cell(180, 7, self._safe_text(f"Tax Amount: {computed_tax:.2f}"), ln=True, align="R")
            pdf.cell(180, 7, self._safe_text(f"Grand Total: {computed_total:.2f}"), ln=True, align="R")
            pdf.set_font("Arial", "", 12)
        else:
            if product is None or qty is None:
                raise ValueError("Either `items` or (`product`, `qty`) must be provided.")

            pdf.cell(60, 8, self._safe_text("Product Name"), 1)
            pdf.cell(60, 8, self._safe_text("Quantity"), 1)
            pdf.cell(60, 8, self._safe_text("Unit Price"), 1)
            pdf.ln()

            pdf.cell(60, 8, self._safe_text(str(product)), 1)
            pdf.cell(60, 8, self._safe_text(str(qty)), 1)
            pdf.cell(60, 8, self._safe_text(f"{unit_price:.2f}" if unit_price is not None else "N/A"), 1)
            pdf.ln()

        if not items:
            pdf.ln(5)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(
                180,
                8,
                self._safe_text(f"Total Amount: {total:.2f}" if total is not None else "Total Amount: N/A"),
                ln=True,
                align="R",
            )

        # Signature + footer (bottom of page)
        pdf.set_y(-48)
        pdf.set_draw_color(160, 160, 160)
        pdf.set_text_color(60, 60, 60)
        pdf.set_font("Arial", "", 10)

        # Signature lines
        left_x = 20
        right_x = 115
        y = pdf.get_y()
        pdf.line(left_x, y, left_x + 70, y)
        pdf.line(right_x, y, right_x + 70, y)
        pdf.ln(2)
        pdf.set_x(left_x)
        pdf.cell(70, 6, self._safe_text("Customer Signature"), 0, 0, "L")
        pdf.set_x(right_x)
        pdf.cell(70, 6, self._safe_text("Authorized Signature"), 0, 1, "L")

        pdf.ln(6)
        pdf.set_font("Arial", "I", 9)
        pdf.set_text_color(110, 110, 110)
        pdf.multi_cell(
            0,
            5,
            self._safe_text(
                "Thank you for shopping with Grocery Mart. Please retain this invoice for future reference."
            ),
            align="C",
        )

        pdf.output(filepath)
