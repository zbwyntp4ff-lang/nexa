"""Email delivery abstraction for auth flows.

Providers are selected via ``EMAIL_PROVIDER`` in settings / ``.env``.
Secrets (SMTP password, API keys) never live in source code.
"""
from __future__ import annotations

import logging
import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config.settings import Settings

logger = logging.getLogger("nexa.auth.email")


class EmailService(ABC):
    """Send transactional email. Implementations must not log secrets."""

    @abstractmethod
    def send(self, *, to: str, subject: str, text_body: str, html_body: str | None = None) -> None:
        """Deliver one message. Raises on hard failure."""


class ConsoleEmailService(EmailService):
    """Development provider: writes the message to the application log."""

    def send(self, *, to: str, subject: str, text_body: str, html_body: str | None = None) -> None:
        logger.info(
            "email[console] to=%s subject=%s\n%s",
            to,
            subject,
            text_body,
        )


class SmtpEmailService(EmailService):
    """SMTP provider configured entirely from environment settings."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        from_address: str,
        use_tls: bool = True,
        use_ssl: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from = from_address
        self._use_tls = use_tls
        self._use_ssl = use_ssl

    def send(self, *, to: str, subject: str, text_body: str, html_body: str | None = None) -> None:
        msg = EmailMessage()
        msg["From"] = self._from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(text_body)
        if html_body:
            msg.add_alternative(html_body, subtype="html")

        if self._use_ssl:
            with smtplib.SMTP_SSL(self._host, self._port, timeout=30) as smtp:
                if self._username:
                    smtp.login(self._username, self._password or "")
                smtp.send_message(msg)
            return

        with smtplib.SMTP(self._host, self._port, timeout=30) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password or "")
            smtp.send_message(msg)


def build_email_service(settings: Settings) -> EmailService:
    provider = (settings.email_provider or "console").strip().lower()
    if provider == "smtp":
        if not settings.smtp_host or not settings.email_from:
            logger.warning("EMAIL_PROVIDER=smtp but SMTP_HOST/EMAIL_FROM missing; using console")
            return ConsoleEmailService()
        return SmtpEmailService(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            from_address=settings.email_from,
            use_tls=settings.smtp_use_tls,
            use_ssl=settings.smtp_use_ssl,
        )
    return ConsoleEmailService()
