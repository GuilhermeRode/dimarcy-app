"""Builds the customer-facing order PDF attached to order e-mails. Mirrors the
layout of frontend/src/pages/ClientPrint.jsx (letterhead, info, one color x size
grid per product, totals, thank-you note).
"""
from pathlib import Path

from fpdf import FPDF

LOGO = Path(__file__).parent / "assets" / "logo-full.png"
NAVY = (13, 42, 82)
MUTED = (92, 108, 138)
LINE = (219, 227, 240)
BG = (238, 242, 249)


def brl(v) -> str:
    return "R$ " + f"{float(v):,.2f}".translate(str.maketrans(",.", ".,"))


def date_br(d) -> str:
    return d.strftime("%d/%m/%Y") if d else "Não definida"


def _t(s) -> str:
    # ponytail: core Helvetica is latin-1 only; odd characters become "?". Embed a TTF if that shows up in practice.
    return str(s).encode("latin-1", "replace").decode("latin-1")


def _groups(order) -> list[list]:
    groups: dict[int, list] = {}
    for i in sorted(order.items, key=lambda x: (x.product.reference, x.color.name)):
        groups.setdefault(i.product_id, []).append(i)
    return list(groups.values())


def build_order_pdf(order) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(True, 15)
    pdf.add_page()
    w = pdf.epw

    # Letterhead: logo | "PEDIDO #00123" | customer + date
    pdf.image(str(LOGO), x=15, y=12, h=24)
    pdf.set_xy(60, 16)
    pdf.set_text_color(*MUTED)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(60, 5, "PEDIDO")
    pdf.set_xy(60, 21)
    pdf.set_text_color(*NAVY)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(60, 10, f"#{order.id:05d}")
    pdf.set_xy(115, 16)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(80, 6, _t(order.customer.name), align="R")
    pdf.set_xy(115, 22)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    pdf.cell(80, 6, date_br(order.date), align="R")
    pdf.set_draw_color(*NAVY)
    pdf.set_line_width(0.8)
    pdf.line(15, 40, 15 + w, 40)
    pdf.set_y(45)

    # Order info, 4 columns
    info = [("DATA DO PEDIDO", date_br(order.date)), ("DATA DE ENTREGA", date_br(order.delivery_date)),
            ("FORMA DE PAGAMENTO", order.payment_method or "-"), ("PRAZO / CONDIÇÃO", order.payment_terms or "-")]
    col = w / 4
    pdf.set_fill_color(*BG)
    pdf.rect(15, pdf.get_y(), w, 16, "F")
    y = pdf.get_y() + 2
    for n, (label, value) in enumerate(info):
        pdf.set_xy(15 + n * col + 3, y)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(*MUTED)
        pdf.cell(col - 6, 5, _t(label))
        pdf.set_xy(15 + n * col + 3, y + 5)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*NAVY)
        pdf.cell(col - 6, 6, _t(value))
    pdf.set_y(y + 20)

    # One color x size grid per product
    pdf.set_line_width(0.2)
    pdf.set_draw_color(*LINE)
    for lines in _groups(order):
        p = lines[0].product
        sizes = list(dict.fromkeys(l.size for l in lines))
        colors = list(dict.fromkeys(l.color_id for l in lines))
        qty = {(l.color_id, l.size): l.quantity for l in lines}
        name = {l.color_id: l.color.name for l in lines}
        if pdf.get_y() > 250:
            pdf.add_page()
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*NAVY)
        pdf.cell(w * 0.75, 7, _t(f"{p.reference}  {p.description}"))
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*MUTED)
        pdf.cell(w * 0.25, 7, f"{brl(lines[0].unit_price)} un.", align="R", new_x="LMARGIN", new_y="NEXT")
        color_w, total_w = 50, 22
        size_w = (w - color_w - total_w) / max(len(sizes), 1)
        pdf.set_fill_color(*BG)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(color_w, 6, "Cor", border="B", fill=True)
        for s in sizes:
            pdf.cell(size_w, 6, _t(s), border="B", fill=True, align="C")
        pdf.cell(total_w, 6, "Total", border="B", fill=True, align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*NAVY)
        for c in colors:
            pdf.cell(color_w, 6, _t(name[c]), border="B")
            for s in sizes:
                pdf.cell(size_w, 6, str(qty.get((c, s)) or "-"), border="B", align="C")
            pdf.cell(total_w, 6, str(sum(q for (cc, _), q in qty.items() if cc == c)), border="B", align="R",
                     new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(w, 7, brl(sum(l.subtotal for l in lines)), align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    # Notes (left) + totals (right)
    if pdf.get_y() > 235:
        pdf.add_page()
    top = pdf.get_y() + 2
    if order.notes:
        pdf.set_xy(15, top)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*NAVY)
        pdf.cell(100, 6, "Observações", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(100, 5, _t(order.notes))
    notes_end = pdf.get_y()
    tx, tw = 15 + w - 70, 70
    pdf.set_y(top)
    rows = [("Peças", str(order.pieces)), ("Subtotal", brl(order.gross)), ("Desconto", brl(order.discount or 0))]
    for label, value in rows:
        pdf.set_x(tx)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*MUTED)
        pdf.cell(tw / 2, 6, _t(label))
        pdf.set_text_color(*NAVY)
        pdf.cell(tw / 2, 6, value, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*NAVY)
    pdf.line(tx, pdf.get_y() + 1, tx + tw, pdf.get_y() + 1)
    pdf.set_xy(tx, pdf.get_y() + 2)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(tw / 2, 9, "Total")
    pdf.cell(tw / 2, 9, brl(order.total), align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(max(pdf.get_y(), notes_end) + 10)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*NAVY)
    pdf.cell(w, 6, "Agradecemos a sua compra e a confiança na Di Marcy!", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(w, 5, _t("Qualquer dúvida sobre este pedido, estamos à disposição."), align="C")
    return bytes(pdf.output())
