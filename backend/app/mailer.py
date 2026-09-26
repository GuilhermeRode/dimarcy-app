"""Sends the admin an e-mail notification when an order is completed (marked as delivered).

Uses Resend's HTTP API (no extra dependency, same style as geocoding.py). If it isn't
configured (resend_api_key empty), sending is skipped and a message is printed instead —
this never blocks the request that triggered it.
"""
import json
import urllib.request

from .config import settings

RESEND_URL = "https://api.resend.com/emails"


def send_order_delivered_email(order) -> None:
    to_addr = settings.notify_email or settings.admin_email
    if not settings.resend_api_key or not settings.mail_from or not to_addr:
        print(f"[mailer] Resend not configured — skipped delivery notification for order #{order.id}.")
        return

    subject = f"Pedido #{order.id:05d} entregue — {order.customer.name}"
    body = (
        f"O pedido #{order.id:05d} foi marcado como ENTREGUE.\n\n"
        f"Cliente: {order.customer.name}\n"
        f"Vendedor: {order.seller.name}\n"
        f"Data do pedido: {order.date}\n"
        f"Peças: {order.pieces}\n"
        f"Total: R$ {order.total:.2f}\n"
    )
    payload = json.dumps({
        "from": settings.mail_from,
        "to": [to_addr],
        "subject": subject,
        "text": body,
    }).encode()
    req = urllib.request.Request(RESEND_URL, data=payload, method="POST", headers={
        "Authorization": f"Bearer {settings.resend_api_key}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
        print(f"[mailer] Delivery notification sent to {to_addr} for order #{order.id}.")
    except Exception as e:  # never let a mail failure break the order update
        print(f"[mailer] Failed to send delivery notification for order #{order.id}: {e}")
