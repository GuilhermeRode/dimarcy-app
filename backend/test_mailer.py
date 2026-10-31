"""Mailer/PDF self-check. Run from backend/:  python test_mailer.py
Builds the order e-mail and PDF from fake data; sends nothing."""
import os
from datetime import date
from types import SimpleNamespace as NS

os.environ.update(RESEND_API_KEY="", FRONTEND_URL="https://app.example.com/")

from app import mailer  # noqa: E402
from app.order_pdf import build_order_pdf  # noqa: E402


def item(ref, color_id, color, size, qty):
    return NS(product_id=hash(ref), product=NS(reference=ref, description="Blusão de tricot xadrez"),
              color_id=color_id, color=NS(name=color), size=size, quantity=qty, unit_price=99.9, subtotal=qty * 99.9)


items = [item("A100", 1, "Bordô", "P", 3), item("A100", 1, "Bordô", "M", 2), item("A100", 2, "Preto", "P", 1),
         item("B200", 3, "Cru", "U", 4)]
order = NS(id=123, date=date(2026, 10, 7), delivery_date=None, status="in_production", payment_method="Boleto",
           payment_terms="30/60", price_table="wholesale", discount=10, notes="Entregar pela manhã.\nLigar antes.", items=items,
           pieces=10, gross=999.0, total=989.0,
           customer=NS(name="Loja <b>Exemplo</b> & Cia"), seller=NS(name="Vendedor Teste", email=None))

pdf = build_order_pdf(order)
assert pdf.startswith(b"%PDF") and len(pdf) > 2000

body = mailer._order_html(order, "Novo pedido", mailer.NAVY, "Pedido #00123 recebido",
                          f"Para <strong>{mailer.html.escape(order.customer.name)}</strong>")
assert 'href="https://app.example.com/#/orders/123"' in body  # HashRouter link, no double slash
assert "07/10/2026" in body and "2026-10-07" not in body
assert "<b>Exemplo</b>" not in body and "&lt;b&gt;Exemplo&lt;/b&gt;" in body
assert "Em produção" in body and "Etapa atual" in body
assert "Etapa atual" not in mailer._order_html(NS(**{**vars(order), "status": "quote"}), "", "", "", "")
assert "07/10/2026" in mailer._order_body(order, "x")
assert mailer._pdf_attachment(order)[0]["filename"] == "pedido-00123.pdf"
assert mailer._with_seller(["a@x.com"], order) == ["a@x.com"]  # seller without e-mail
assert mailer._with_seller(["a@x.com"], NS(seller=NS(email="v@x.com"))) == ["a@x.com", "v@x.com"]
assert mailer._with_seller(["a@x.com"], NS(seller=NS(email="a@x.com"))) == ["a@x.com"]  # no duplicate

# the customer's copy goes out unless the order was saved with "Enviar e-mail ao cliente" off
sent = []
real_send, mailer._send = mailer._send, lambda subject, text, body, to, attachments=None: sent.append(to) or True
for flag, expected in ((True, [["cli@x.com"]]), (False, [])):
    sent.clear()
    mailer._notify_customer(NS(**{**vars(order), "customer": NS(name="Loja", email="cli@x.com"), "notify_customer": flag}),
                            "Test", "Assunto", "Mensagem.", "Badge", mailer.NAVY, "Título")
    assert sent == expected, (flag, sent)
# a retail order sends nothing, to anyone
sent.clear()
retail = NS(**{**vars(order), "price_table": "retail", "notify_customer": True, "customer": NS(name="Maria", email="cli@x.com"),
               "seller": NS(name="V", email="v@x.com")})
mailer.send_order_created_emails(retail)
mailer.send_order_updated_emails(retail)
mailer.send_order_delivered_email(retail)
assert sent == [], sent
mailer._send = real_send
print("mailer OK")
