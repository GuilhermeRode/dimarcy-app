"""Sends the admin an e-mail notification when an order is completed (marked as delivered).

Uses plain smtplib (no extra dependency). If SMTP isn't configured (smtp_host empty),
sending is skipped and a message is printed instead — this never blocks the request
that triggered it.
"""
import smtplib
from email.mime.text import MIMEText

from .config import settings


def send_order_delivered_email(order) -> None:
    to_addr = settings.notify_email or settings.admin_email
    if not settings.smtp_host or not to_addr:
        print(f"[mailer] SMTP not configured — skipped delivery notification for order #{order.id}.")
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
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user or to_addr
    msg["To"] = to_addr

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(msg["From"], [to_addr], msg.as_string())
        print(f"[mailer] Delivery notification sent to {to_addr} for order #{order.id}.")
    except Exception as e:  # never let a mail failure break the order update
        print(f"[mailer] Failed to send delivery notification for order #{order.id}: {e}")
