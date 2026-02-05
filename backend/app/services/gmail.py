"""
Gmail API Service

Implements OAuth 2.0 flow for Gmail API and email sending.
This satisfies PRD G5 requirement: Google Workspace API connectivity.

Benefits over SMTP:
- Better deliverability (sent from user's actual Gmail)
- OAuth 2.0 security (no passwords stored)
- Built-in tracking support
- Access to Gmail features (labels, threads)
"""

import base64
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Gmail API scopes
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
]


@dataclass
class GmailTokens:
    """OAuth tokens for Gmail API."""

    access_token: str
    refresh_token: str
    token_uri: str
    client_id: str
    client_secret: str
    expiry: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_uri": self.token_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "expiry": self.expiry.isoformat() if self.expiry else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GmailTokens":
        """Create from dictionary."""
        expiry = None
        if data.get("expiry"):
            expiry = datetime.fromisoformat(data["expiry"])
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            token_uri=data["token_uri"],
            client_id=data["client_id"],
            client_secret=data["client_secret"],
            expiry=expiry,
        )


@dataclass
class GmailSendResult:
    """Result of sending an email via Gmail API."""

    success: bool
    message_id: str | None = None
    thread_id: str | None = None
    error: str | None = None
    sent_at: datetime | None = None


class GmailService:
    """Service for Gmail API operations."""

    def __init__(self, tokens: GmailTokens):
        """Initialize with OAuth tokens."""
        self.tokens = tokens
        self._service = None

    @classmethod
    def create_oauth_flow(cls, redirect_uri: str | None = None) -> Flow:
        """
        Create OAuth 2.0 flow for Gmail authorization.

        Args:
            redirect_uri: OAuth redirect URI (defaults to settings)

        Returns:
            Google OAuth Flow object
        """
        client_config = {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri or settings.gmail_redirect_uri],
            }
        }

        flow = Flow.from_client_config(
            client_config,
            scopes=GMAIL_SCOPES,
            redirect_uri=redirect_uri or settings.gmail_redirect_uri,
        )

        return flow

    @classmethod
    def get_authorization_url(cls, state: str | None = None) -> tuple[str, str]:
        """
        Get the OAuth authorization URL.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Tuple of (authorization_url, state)
        """
        flow = cls.create_oauth_flow()
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",  # Force consent to get refresh token
            state=state,
        )
        return authorization_url, state

    @classmethod
    def exchange_code(cls, code: str) -> GmailTokens:
        """
        Exchange authorization code for tokens.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            GmailTokens object
        """
        flow = cls.create_oauth_flow()
        flow.fetch_token(code=code)

        credentials = flow.credentials
        return GmailTokens(
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_uri=credentials.token_uri,
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
            expiry=credentials.expiry,
        )

    def _get_credentials(self) -> Credentials:
        """Get valid credentials, refreshing if necessary."""
        creds = Credentials(
            token=self.tokens.access_token,
            refresh_token=self.tokens.refresh_token,
            token_uri=self.tokens.token_uri,
            client_id=self.tokens.client_id,
            client_secret=self.tokens.client_secret,
        )

        # Refresh if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Update stored tokens
            self.tokens.access_token = creds.token
            self.tokens.expiry = creds.expiry

        return creds

    def _get_service(self):
        """Get Gmail API service instance."""
        if not self._service:
            creds = self._get_credentials()
            self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def get_user_email(self) -> str | None:
        """Get the authenticated user's email address."""
        try:
            service = self._get_service()
            profile = service.users().getProfile(userId="me").execute()
            return profile.get("emailAddress")
        except HttpError:
            logger.exception("[gmail] Error getting user email")
            return None

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        from_name: str | None = None,
        reply_to: str | None = None,
        tracking_pixel_url: str | None = None,
    ) -> GmailSendResult:
        """
        Send an email via Gmail API.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body_html: HTML body content
            from_name: Display name for sender (optional)
            reply_to: Reply-to address (optional)
            tracking_pixel_url: URL for tracking pixel (optional)

        Returns:
            GmailSendResult with message ID and status
        """
        try:
            service = self._get_service()
            user_email = self.get_user_email()

            if not user_email:
                return GmailSendResult(
                    success=False,
                    error="Could not determine sender email address",
                )

            # Create message
            message = MIMEMultipart("alternative")
            message["To"] = to_email
            message["Subject"] = subject

            if from_name:
                message["From"] = f"{from_name} <{user_email}>"
            else:
                message["From"] = user_email

            if reply_to:
                message["Reply-To"] = reply_to

            # Add tracking pixel if provided
            if tracking_pixel_url:
                body_html = body_html.replace(
                    "</body>",
                    f'<img src="{tracking_pixel_url}" width="1" height="1" style="display:none" /></body>',
                )

            html_part = MIMEText(body_html, "html")
            message.attach(html_part)

            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

            # Send
            sent_message = (
                service.users()
                .messages()
                .send(userId="me", body={"raw": raw_message})
                .execute()
            )

            return GmailSendResult(
                success=True,
                message_id=sent_message.get("id"),
                thread_id=sent_message.get("threadId"),
                sent_at=datetime.utcnow(),
            )

        except HttpError as e:
            error_message = str(e)
            if e.resp.status == 401:
                error_message = "Gmail authentication expired. Please re-connect your Gmail account."
            elif e.resp.status == 403:
                error_message = "Gmail access denied. Please grant email sending permissions."
            return GmailSendResult(success=False, error=error_message)
        except Exception as e:
            return GmailSendResult(success=False, error=str(e))

    async def send_email_async(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        from_name: str | None = None,
        reply_to: str | None = None,
        tracking_pixel_url: str | None = None,
    ) -> GmailSendResult:
        """
        Async wrapper for send_email.

        Uses run_in_executor since the Google API client is synchronous.
        """
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.send_email(
                to_email=to_email,
                subject=subject,
                body_html=body_html,
                from_name=from_name,
                reply_to=reply_to,
                tracking_pixel_url=tracking_pixel_url,
            ),
        )


def is_gmail_configured() -> bool:
    """Check if Gmail API credentials are configured."""
    return bool(settings.google_client_id and settings.google_client_secret)


async def send_email_via_gmail(
    tokens: GmailTokens,
    to_email: str,
    subject: str,
    body_html: str,
    from_name: str | None = None,
    reply_to: str | None = None,
    tracking_pixel_url: str | None = None,
) -> GmailSendResult:
    """
    Convenience function to send email via Gmail API.

    Args:
        tokens: OAuth tokens for the user
        to_email: Recipient email
        subject: Email subject
        body_html: HTML body
        from_name: Display name for sender
        reply_to: Reply-to address
        tracking_pixel_url: URL for tracking pixel

    Returns:
        GmailSendResult
    """
    service = GmailService(tokens)
    return await service.send_email_async(
        to_email=to_email,
        subject=subject,
        body_html=body_html,
        from_name=from_name,
        reply_to=reply_to,
        tracking_pixel_url=tracking_pixel_url,
    )
