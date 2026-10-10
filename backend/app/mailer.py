"""Sends e-mail notifications via Resend's HTTP API (no extra dependency, same
style as geocoding.py). If it isn't configured (resend_api_key empty), sending
is skipped and a message is printed instead — this never blocks the request
that triggered it.
"""
import base64
import html
import json
import urllib.error
import urllib.request

from .config import settings
from .order_pdf import build_order_pdf

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
ACCENT_STRONG = "#1d54c9"
BG = "#eef2f9"
BOX_BG = "#f6f8fb"
TEXT = "#334155"
MUTED = "#5c6c8a"
LINE = "#dbe3f0"
DELIVERED_COLOR = "#1c7a52"
SERIF = "Georgia,'Times New Roman',serif"

# Progress bar shown on order e-mails; quote/canceled orders show no bar.
ORDER_STEPS = [("confirmed", "Confirmado"), ("in_production", "Em produção"),
               ("shipped", "Enviado"), ("delivered", "Entregue")]

# Icon + wordmark side by side; lives in frontend/public so the Deploy workflow publishes it.
LOGO_URL = "https://app.dimarcy.com.br/email-logo.png"


def _send(subject: str, text: str, html_body: str, to: list[str], attachments: list[dict] | None = None) -> bool:
    if not settings.resend_api_key or not settings.mail_from or not to:
        return False
    body = {
        "from": settings.mail_from,
        "to": to,
        "reply_to": REPLY_TO,
        "subject": subject,
        "text": text,
        "html": html_body,
    }
    if attachments:
        body["attachments"] = attachments
    req = urllib.request.Request(RESEND_URL, data=json.dumps(body).encode(), method="POST", headers={
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


def _date_br(d) -> str:
    return d.strftime("%d/%m/%Y")


def _order_url(order) -> str:
    # The app uses HashRouter, so routes live after "#".
    return f"{settings.frontend_url.rstrip('/')}/#/orders/{order.id}"


def _pdf_attachment(order) -> list[dict] | None:
    try:
        content = base64.b64encode(build_order_pdf(order)).decode()
    except Exception as e:  # a broken PDF must not stop the e-mail itself
        print(f"[mailer] Failed to build PDF for order #{order.id}: {e}")
        return None
    return [{"filename": f"pedido-{order.id:05d}.pdf", "content": content}]


def _layout(badge: str, badge_color: str, title: str, inner: str) -> str:
    """Shared shell: logo above a white card with a navy top bar, footer below. Empty badge = no badge."""
    badge_html = (f'<div style="margin-bottom:12px;font-size:12px;font-weight:bold;letter-spacing:1.5px;'
                  f'text-transform:uppercase;color:{badge_color};">&#9679;&nbsp; {html.escape(badge)}</div>'
                  if badge else "")
    return f"""\
<div style="background:{BG};padding:32px 16px;font-family:Arial,Helvetica,sans-serif;">
  <div style="max-width:600px;margin:0 auto;">
    <div style="text-align:center;padding-bottom:20px;">
      <img src="{LOGO_URL}" alt="Di Marcy" width="220" style="display:inline-block;height:auto;border:0;">
    </div>
    <div style="background:#ffffff;border:1px solid {LINE};border-top:4px solid {NAVY};padding:40px 32px;">
      {badge_html}
      <h1 style="margin:0 0 16px;font-family:{SERIF};font-weight:normal;font-size:28px;color:{NAVY};">
        {html.escape(title)}</h1>
{inner}
    </div>
    <p style="margin:20px 8px 0;color:{MUTED};font-size:12px;line-height:1.6;">
      Di Marcy Pedidos &middot; Mensagem automática, não é necessário responder.<br>
      Dúvidas? Fale com seu vendedor ou
      <a href="mailto:{REPLY_TO}" style="color:{NAVY};">{REPLY_TO}</a>
    </p>
  </div>
</div>"""


def _button(url: str, label: str) -> str:
    return (f'<a href="{html.escape(url)}" style="display:inline-block;background:{NAVY};color:#ffffff;'
            f'font-size:14px;font-weight:bold;text-decoration:none;padding:14px 28px;border-radius:4px;">'
            f'{html.escape(label)}</a>')


def _steps_html(status: str) -> str:
    keys = [k for k, _ in ORDER_STEPS]
    if status not in keys:
        return ""
    current = keys.index(status)
    cells = []
    for n, (_, label) in enumerate(ORDER_STEPS):
        reached = n <= current
        sub = "Etapa atual" if n == current else "Próxima etapa" if n == current + 1 else "&nbsp;"
        cells.append(
            f'<td width="25%" style="padding-right:{6 if n < len(ORDER_STEPS) - 1 else 0}px;vertical-align:top;">'
            f'<div style="height:3px;background:{NAVY if reached else LINE};font-size:0;line-height:0;">&nbsp;</div>'
            f'<div style="padding-top:8px;font-size:13px;font-weight:bold;color:{NAVY if reached else MUTED};">'
            f'{label}</div><div style="font-size:12px;color:{MUTED};">{sub}</div></td>')
    return ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 28px;">'
            f'<tr>{"".join(cells)}</tr></table>')


def _order_body(order, heading: str) -> str:
    return (
        f"{heading}\n\n"
        f"Cliente: {order.customer.name}\n"
        f"Vendedor: {order.seller.name}\n"
        f"Data do pedido: {_date_br(order.date)}\n"
        f"Peças: {order.pieces}\n"
        f"Total: R$ {_brl(order.total)}\n\n"
        f"O pedido completo segue em PDF anexo.\n"
        f"Ver pedido: {_order_url(order)}\n"
    )


def _order_html(order, badge: str, badge_color: str, title: str, intro_html: str) -> str:
    def field(label, value):
        return (f'<td width="50%" style="padding-bottom:16px;vertical-align:top;">'
                f'<div style="font-size:11px;letter-spacing:1px;text-transform:uppercase;color:{MUTED};">{label}</div>'
                f'<div style="padding-top:4px;font-size:15px;color:{NAVY};">{html.escape(str(value))}</div></td>')
    return _layout(badge, badge_color, title, f"""\
      <p style="margin:0 0 28px;font-size:15px;line-height:1.6;color:{TEXT};">{intro_html}</p>
      {_steps_html(order.status)}
      <div style="background:{BOX_BG};border:1px solid {LINE};padding:24px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>{field("Cliente", order.customer.name)}{field("Vendedor", order.seller.name)}</tr>
          <tr>{field("Data do pedido", _date_br(order.date))}{field("Peças", order.pieces)}</tr>
        </table>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid {LINE};">
          <tr><td style="padding-top:20px;font-size:13px;font-weight:bold;letter-spacing:1px;color:{NAVY};">TOTAL</td>
          <td style="padding-top:20px;text-align:right;font-family:{SERIF};font-size:28px;font-weight:bold;
                     color:{NAVY};white-space:nowrap;">R$ {_brl(order.total)}</td></tr>
        </table>
      </div>
      <p style="margin:12px 0 0;font-size:13px;color:{MUTED};">O pedido completo segue em PDF anexo.</p>
      <div style="padding-top:28px;">{_button(_order_url(order), "Ver pedido")}</div>""")


def send_password_reset_email(to_email: str, reset_url: str) -> bool:
    subject = "Redefinir senha — Di Marcy Pedidos"
    text = (
        f"Recebemos um pedido para redefinir sua senha.\n\n"
        f"Abra este link para escolher uma nova senha (válido por 30 minutos):\n{reset_url}\n\n"
        f"Se você não pediu isso, pode ignorar este e-mail."
    )
    body_html = _layout("", "", "Redefinir sua senha", f"""\
      <p style="margin:0 0 28px;font-size:15px;line-height:1.6;color:{TEXT};">Recebemos um pedido para redefinir
        sua senha. Clique no botão abaixo para escolher uma nova. O link vale por 30 minutos.</p>
      {_button(reset_url, "Redefinir senha")}
      <p style="margin:28px 0 0;font-size:13px;color:{MUTED};">Se você não pediu isso, pode ignorar este e-mail —
        sua senha continua a mesma.</p>""")
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
    heading = f"Um novo pedido para {order.customer.name} foi criado por {order.seller.name} em {_date_br(order.date)}."
    intro = (f"Um novo pedido para <strong>{html.escape(order.customer.name)}</strong> foi criado por "
             f"{html.escape(order.seller.name)} em {_date_br(order.date)}.")
    body_html = _order_html(order, "Novo pedido", ACCENT_STRONG, f"Pedido #{order.id:05d} recebido", intro)
    try:
        if _send(subject, _order_body(order, heading), body_html, to, _pdf_attachment(order)):
            print(f"[mailer] Order-created notification sent to {to} for order #{order.id}.")
        else:
            print(f"[mailer] Resend not configured — skipped order-created notification for order #{order.id}.")
    except Exception as e:  # never let a mail failure break the order creation
        print(f"[mailer] Failed to send order-created notification for order #{order.id}: {e}")


def send_order_delivered_email(order) -> None:
    to_addr = settings.notify_email or settings.admin_email
    subject = f"Pedido #{order.id:05d} entregue — {order.customer.name}"
    heading = f"O pedido de {order.customer.name} foi marcado como entregue."
    intro = f"O pedido de <strong>{html.escape(order.customer.name)}</strong> foi marcado como entregue."
    body_html = _order_html(order, "Pedido entregue", DELIVERED_COLOR, f"Pedido #{order.id:05d} entregue", intro)
    try:
        if _send(subject, _order_body(order, heading), body_html, [to_addr], _pdf_attachment(order)):
            print(f"[mailer] Delivery notification sent to {to_addr} for order #{order.id}.")
        else:
            print(f"[mailer] Resend not configured — skipped delivery notification for order #{order.id}.")
    except Exception as e:  # never let a mail failure break the order update
        print(f"[mailer] Failed to send delivery notification for order #{order.id}: {e}")
