import smtplib
from email.message import EmailMessage

from ..services.config import (
    SMTP_FROM_EMAIL,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USE_SSL,
    SMTP_USE_TLS,
    SMTP_USERNAME,
)


class MailNotConfiguredError(RuntimeError):
    pass


def send_email(*, recipient: str, subject: str, body: str) -> None:
    if not SMTP_HOST:
        raise MailNotConfiguredError("Email service is not configured")
    message = EmailMessage()
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    smtp_class = smtplib.SMTP_SSL if SMTP_USE_SSL else smtplib.SMTP
    try:
        with smtp_class(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            if SMTP_USE_TLS and not SMTP_USE_SSL:
                smtp.starttls()
            if SMTP_USERNAME:
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        raise MailNotConfiguredError("Email delivery failed") from None
