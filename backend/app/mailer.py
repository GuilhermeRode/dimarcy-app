"""Sends e-mail notifications via Resend's HTTP API (no extra dependency, same
style as geocoding.py). If it isn't configured (resend_api_key empty), sending
is skipped and a message is printed instead — this never blocks the request
that triggered it.
"""
import html
import json
import urllib.error
import urllib.request

from .config import settings

RESEND_URL = "https://api.resend.com/emails"

# Fixed business inboxes that must be copied on every new order — not
# environment-specific, so no .env entry for these.
ORDER_CREATED_RECIPIENTS = ["dimarcypedidos@gmail.com", "di_marcy@hotmail.com"]

# Resend requires "from" on a domain verified with them (gmail.com can't be
# verified), so replies are routed back to the real inbox via Reply-To.
REPLY_TO = "dimarcypedidos@gmail.com"

# Brand palette, matching frontend/src/styles.css (:root custom properties) —
# email clients don't support CSS variables, so the values are copied in here.
NAVY = "#0d2a52"
ACCENT = "#2f6fed"
ACCENT_STRONG = "#1d54c9"
ACCENT_LIGHT = "#e8f0fe"
BG = "#eef2f9"
MUTED = "#5c6c8a"
LINE = "#dbe3f0"
DELIVERED_BG = "#e0f1ea"
DELIVERED_COLOR = "#1c7a52"

LOGO_URL = "https://app.dimarcy.com.br/uploads/branding/logo-wordmark.png"


def _send(subject: str, text: str, html_body: str, to: list[str]) -> bool:
    if not settings.resend_api_key or not settings.mail_from or not to:
        return False
    payload = json.dumps({
        "from": settings.mail_from,
        "to": to,
        "reply_to": REPLY_TO,
        "subject": subject,
        "text": text,
        "html": html_body,
    }).encode()
    req = urllib.request.Request(RESEND_URL, data=payload, method="POST", headers={
        "Authorization": f"Bearer {settings.resend_api_key}",
        "Content-Type": "application/json",
        # Cloudflare (fronting api.resend.com) blocks urllib's default
        # "Python-urllib/x.y" User-Agent as a bot signature (error 1010).
        "User-Agent": "dimarcy-pedidos-backend/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code} {e.reason}: {e.read().decode(errors='replace')}") from None
    return True


def _brl(v: float) -> str:
    return f"{v:,.2f}".translate(str.maketrans(",.", ".,"))


def _order_body(order, heading: str) -> str:
    return (
        f"{heading}\n\n"
        f"Cliente: {order.customer.name}\n"
        f"Vendedor: {order.seller.name}\n"
        f"Data do pedido: {order.date}\n"
        f"Peças: {order.pieces}\n"
        f"Total: R$ {_brl(order.total)}\n"
    )


def _order_html(order, heading: str, status_label: str, status_bg: str, status_color: str) -> str:
    rows = "".join(
        f'<tr><td style="padding:8px 0;color:{MUTED};font-size:14px;border-bottom:1px solid {LINE};">{label}</td>'
        f'<td style="padding:8px 0;color:{NAVY};font-size:14px;text-align:right;border-bottom:1px solid {LINE};">'
        f'{html.escape(str(value))}</td></tr>'
        for label, value in [
            ("Cliente", order.customer.name),
            ("Vendedor", order.seller.name),
            ("Data do pedido", order.date),
            ("Peças", order.pieces),
        ]
    )
    return f"""\
<div style="background:{BG};padding:24px;font-family:Arial,Helvetica,sans-serif;">
  <div style="max-width:480px;margin:0 auto;background:#ffffff;border-radius:8px;overflow:hidden;border:1px solid {LINE};">
    <div style="background:#ffffff;padding:24px 24px 16px;text-align:center;border-bottom:3px solid {ACCENT};">
      <img src="{LOGO_URL}" alt="Di Marcy" width="140" style="display:block;margin:0 auto;height:auto;">
    </div>
    <div style="padding:16px 24px 0;text-align:center;">
      <span style="display:inline-block;background:{status_bg};color:{status_color};font-size:12px;
                   font-weight:bold;letter-spacing:0.5px;text-transform:uppercase;padding:6px 14px;
                   border-radius:999px;">{html.escape(status_label)}</span>
    </div>
    <div style="padding:20px 24px 24px;">
      <h1 style="margin:0 0 4px;color:{NAVY};font-size:20px;text-align:center;">Pedido #{order.id:05d}</h1>
      <p style="margin:0 0 20px;color:{MUTED};font-size:14px;text-align:center;">{html.escape(heading)}</p>
      <table style="width:100%;border-collapse:collapse;">{rows}</table>
      <div style="margin-top:24px;padding:20px;background:{BG};border-radius:8px;text-align:center;">
        <div style="color:{MUTED};font-size:12px;font-weight:bold;letter-spacing:0.5px;text-transform:uppercase;">
          Total do pedido</div>
        <div style="margin-top:8px;color:{ACCENT_STRONG};font-size:30px;font-weight:bold;">R$ {_brl(order.total)}</div>
      </div>
    </div>
    <div style="padding:16px 24px;text-align:center;border-top:1px solid {LINE};">
      <p style="margin:0;color:{MUTED};font-size:12px;">Di Marcy Pedidos</p>
    </div>
  </div>
</div>"""


def send_password_reset_email(to_email: str, reset_url: str) -> bool:
    subject = "Redefinir senha — Di Marcy Pedidos"
    text = (
        f"Recebemos um pedido para redefinir sua senha.\n\n"
        f"Abra este link para escolher uma nova senha (válido por 30 minutos):\n{reset_url}\n\n"
        f"Se você não pediu isso, pode ignorar este e-mail."
    )
    body_html = f"""\
<div style="background:{BG};padding:24px;font-family:Arial,Helvetica,sans-serif;">
  <div style="max-width:480px;margin:0 auto;background:#ffffff;border-radius:8px;overflow:hidden;border:1px solid {LINE};">
    <div style="background:#ffffff;padding:24px 24px 16px;text-align:center;border-bottom:3px solid {ACCENT};">
      <img src="{LOGO_URL}" alt="Di Marcy" width="140" style="display:block;margin:0 auto;height:auto;">
    </div>
    <div style="padding:24px;text-align:center;">
      <h1 style="margin:0 0 12px;color:{NAVY};font-size:18px;">Redefinir sua senha</h1>
      <p style="margin:0 0 20px;color:{MUTED};font-size:14px;">Clique no botão abaixo para escolher uma nova senha.
        O link vale por 30 minutos.</p>
      <a href="{html.escape(reset_url)}" style="display:inline-block;background:{ACCENT};color:#ffffff;
         font-size:14px;font-weight:bold;text-decoration:none;padding:12px 28px;border-radius:6px;">
        Redefinir senha</a>
      <p style="margin:24px 0 0;color:{MUTED};font-size:12px;">Se você não pediu isso, pode ignorar este e-mail —
        sua senha continua a mesma.</p>
    </div>
  </div>
</div>"""
    try:
        sent = _send(subject, text, body_html, [to_email])
        print(f"[mailer] Password reset email {'sent to' if sent else 'skipped (Resend not configured) for'} {to_email}.")
        return sent
    except Exception as e:  # never let a mail failure leak whether the account exists
        print(f"[mailer] Failed to send password reset email to {to_email}: {e}")
        return False


def send_order_created_emails(order) -> None:
    to = list(ORDER_CREATED_RECIPIENTS)
    if order.seller.email:
        to.append(order.seller.email)
    subject = f"Pedido #{order.id:05d} criado — {order.customer.name}"
    heading = f"Um novo pedido foi criado por {order.seller.name}."
    text = _order_body(order, heading)
    body_html = _order_html(order, heading, "Novo pedido", ACCENT_LIGHT, ACCENT_STRONG)
    try:
        if _send(subject, text, body_html, to):
            print(f"[mailer] Order-created notification sent to {to} for order #{order.id}.")
        else:
            print(f"[mailer] Resend not configured — skipped order-created notification for order #{order.id}.")
    except Exception as e:  # never let a mail failure break the order creation
        print(f"[mailer] Failed to send order-created notification for order #{order.id}: {e}")


def send_order_delivered_email(order) -> None:
    to_addr = settings.notify_email or settings.admin_email
    subject = f"Pedido #{order.id:05d} entregue — {order.customer.name}"
    heading = "O pedido foi marcado como ENTREGUE."
    text = _order_body(order, heading)
    body_html = _order_html(order, heading, "Pedido entregue", DELIVERED_BG, DELIVERED_COLOR)
    try:
        if _send(subject, text, body_html, [to_addr]):
            print(f"[mailer] Delivery notification sent to {to_addr} for order #{order.id}.")
        else:
            print(f"[mailer] Resend not configured — skipped delivery notification for order #{order.id}.")
    except Exception as e:  # never let a mail failure break the order update
        print(f"[mailer] Failed to send delivery notification for order #{order.id}: {e}")
