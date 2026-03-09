"""
Gmail Inbox Monitoring Service

Monitors a user's Gmail inbox for CRE-related emails (flyers, OMs, property listings)
and automatically processes attachments into the deal pipeline.
"""

import asyncio
import base64
import logging
import os
import re
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.db.models.deal import Deal, DealStage, Property
from app.db.models.document import ParsedDocument, DocumentType, DocumentStatus
from app.services.gmail import GmailTokens, GmailService

logger = logging.getLogger(__name__)

# Subject patterns that indicate CRE-related emails
CRE_SUBJECT_PATTERNS = [
    "flyer",
    "om",
    "offering memorandum",
    "lease",
    "retail",
    "property",
    "investment",
    "nnn",
    "available",
    "for sale",
]

# Build a regex pattern for matching subjects (case-insensitive)
CRE_SUBJECT_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in CRE_SUBJECT_PATTERNS) + r")\b",
    re.IGNORECASE,
)

# MIME types we extract as attachments
ATTACHMENT_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/tiff",
}


class GmailMonitorService:
    """Service for monitoring Gmail inbox for CRE-related emails."""

    def __init__(self, tokens: GmailTokens):
        """
        Initialize with Gmail OAuth tokens.

        Args:
            tokens: GmailTokens containing OAuth credentials.
        """
        self.tokens = tokens
        self.gmail_service = GmailService(tokens)
        self._api_service = None

    def _get_api_service(self):
        """Get the underlying Gmail API service, lazily initialized."""
        if self._api_service is None:
            self._api_service = self.gmail_service._get_service()
        return self._api_service

    async def check_inbox(
        self,
        labels: list[str] | None = None,
        max_results: int = 20,
    ) -> list[dict]:
        """
        Fetch unread emails matching CRE patterns from the inbox.

        Searches for unread messages whose subjects contain CRE-related
        keywords (flyer, OM, offering memorandum, lease, retail, property,
        investment, NNN, available, for sale).

        Args:
            labels: Optional list of Gmail label IDs to filter by.
                    Defaults to ["INBOX"].
            max_results: Maximum number of messages to return. Defaults to 20.

        Returns:
            List of message dicts with keys: id, subject, from, date, has_attachments.
        """
        loop = asyncio.get_event_loop()

        def _fetch():
            service = self._get_api_service()

            # Build query string for CRE-related subjects
            subject_queries = " OR ".join(
                f"subject:{pattern}" for pattern in CRE_SUBJECT_PATTERNS
            )
            query = f"is:unread ({subject_queries})"

            label_ids = labels or ["INBOX"]

            try:
                response = (
                    service.users()
                    .messages()
                    .list(
                        userId="me",
                        q=query,
                        labelIds=label_ids,
                        maxResults=max_results,
                    )
                    .execute()
                )
            except Exception:
                logger.exception("[gmail_monitor] Error listing messages")
                return []

            messages = response.get("messages", [])
            if not messages:
                logger.info("[gmail_monitor] No matching unread messages found")
                return []

            results = []
            for msg_stub in messages:
                try:
                    msg = (
                        service.users()
                        .messages()
                        .get(userId="me", id=msg_stub["id"], format="metadata")
                        .execute()
                    )
                    headers = {
                        h["name"].lower(): h["value"]
                        for h in msg.get("payload", {}).get("headers", [])
                    }

                    # Check for attachments by looking at payload parts
                    has_attachments = False
                    payload = msg.get("payload", {})
                    parts = payload.get("parts", [])
                    for part in parts:
                        if part.get("filename") and part.get("body", {}).get(
                            "attachmentId"
                        ):
                            has_attachments = True
                            break

                    results.append(
                        {
                            "id": msg["id"],
                            "subject": headers.get("subject", "(no subject)"),
                            "from": headers.get("from", ""),
                            "date": headers.get("date", ""),
                            "has_attachments": has_attachments,
                        }
                    )
                except Exception:
                    logger.exception(
                        "[gmail_monitor] Error fetching message %s",
                        msg_stub["id"],
                    )

            logger.info(
                "[gmail_monitor] Found %d matching messages", len(results)
            )
            return results

        return await loop.run_in_executor(None, _fetch)

    async def extract_attachments(self, message_id: str) -> list[dict]:
        """
        Pull PDF and image attachments from a Gmail message.

        Args:
            message_id: The Gmail message ID.

        Returns:
            List of dicts with keys: filename, data (bytes), mime_type.
        """
        loop = asyncio.get_event_loop()

        def _extract():
            service = self._get_api_service()
            attachments = []

            try:
                msg = (
                    service.users()
                    .messages()
                    .get(userId="me", id=message_id, format="full")
                    .execute()
                )
            except Exception:
                logger.exception(
                    "[gmail_monitor] Error fetching message %s for attachments",
                    message_id,
                )
                return []

            parts = msg.get("payload", {}).get("parts", [])

            for part in parts:
                mime_type = part.get("mimeType", "")
                filename = part.get("filename", "")
                attachment_id = part.get("body", {}).get("attachmentId")

                if not filename or not attachment_id:
                    continue

                if mime_type not in ATTACHMENT_MIME_TYPES:
                    continue

                try:
                    attachment = (
                        service.users()
                        .messages()
                        .attachments()
                        .get(
                            userId="me",
                            messageId=message_id,
                            id=attachment_id,
                        )
                        .execute()
                    )

                    data = base64.urlsafe_b64decode(
                        attachment["data"].encode("UTF-8")
                    )

                    attachments.append(
                        {
                            "filename": filename,
                            "data": data,
                            "mime_type": mime_type,
                        }
                    )
                    logger.info(
                        "[gmail_monitor] Extracted attachment: %s (%s, %d bytes)",
                        filename,
                        mime_type,
                        len(data),
                    )
                except Exception:
                    logger.exception(
                        "[gmail_monitor] Error extracting attachment %s from message %s",
                        filename,
                        message_id,
                    )

            return attachments

        return await loop.run_in_executor(None, _extract)

    async def process_flyer_email(
        self,
        message_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> dict:
        """
        Full pipeline: extract attachments from a CRE email, save files,
        create a Property record, and create a Deal in INTAKE stage.

        Args:
            message_id: The Gmail message ID to process.
            user_id: The user ID who owns this deal.
            db: Async database session.

        Returns:
            Summary dict with keys: property_id, deal_id, attachments_saved,
            subject, errors.
        """
        errors: list[str] = []
        attachments_saved: list[str] = []

        # Fetch message metadata for subject and body
        loop = asyncio.get_event_loop()

        def _get_message_details():
            service = self._get_api_service()
            try:
                msg = (
                    service.users()
                    .messages()
                    .get(userId="me", id=message_id, format="full")
                    .execute()
                )
                headers = {
                    h["name"].lower(): h["value"]
                    for h in msg.get("payload", {}).get("headers", [])
                }
                # Extract plain text body
                body_text = ""
                payload = msg.get("payload", {})
                if payload.get("body", {}).get("data"):
                    body_text = base64.urlsafe_b64decode(
                        payload["body"]["data"]
                    ).decode("utf-8", errors="replace")
                else:
                    for part in payload.get("parts", []):
                        if part.get("mimeType") == "text/plain" and part.get(
                            "body", {}
                        ).get("data"):
                            body_text = base64.urlsafe_b64decode(
                                part["body"]["data"]
                            ).decode("utf-8", errors="replace")
                            break

                return {
                    "subject": headers.get("subject", "(no subject)"),
                    "from": headers.get("from", ""),
                    "date": headers.get("date", ""),
                    "body": body_text,
                }
            except Exception:
                logger.exception(
                    "[gmail_monitor] Error getting message details for %s",
                    message_id,
                )
                return None

        msg_details = await loop.run_in_executor(None, _get_message_details)
        if not msg_details:
            return {
                "property_id": None,
                "deal_id": None,
                "attachments_saved": [],
                "subject": None,
                "errors": ["Failed to fetch message details"],
            }

        subject = msg_details["subject"]

        # Extract and save attachments
        attachments = await self.extract_attachments(message_id)

        upload_dir = os.path.abspath(settings.upload_dir)
        os.makedirs(upload_dir, exist_ok=True)

        for attachment in attachments:
            try:
                safe_filename = f"{uuid.uuid4()}_{attachment['filename']}"
                file_path = os.path.join(upload_dir, safe_filename)
                with open(file_path, "wb") as f:
                    f.write(attachment["data"])
                attachments_saved.append(file_path)
                logger.info(
                    "[gmail_monitor] Saved attachment to %s", file_path
                )
            except Exception as e:
                error_msg = f"Failed to save attachment {attachment['filename']}: {e}"
                logger.error("[gmail_monitor] %s", error_msg)
                errors.append(error_msg)

        # Create Property record from email subject/body
        property_name = subject.strip() or "Imported Property"
        property_id = str(uuid.uuid4())

        new_property = Property(
            id=property_id,
            user_id=user_id,
            name=property_name,
            address="(pending extraction)",
            city="(pending)",
            state="(pending)",
            zip_code="(pending)",
            property_type="retail",
            source_type="email",
            notes=f"Imported from email: {subject}\nFrom: {msg_details['from']}\n"
            f"Date: {msg_details['date']}",
        )
        db.add(new_property)

        # Create Deal in INTAKE stage
        deal_id = str(uuid.uuid4())
        new_deal = Deal(
            id=deal_id,
            user_id=user_id,
            property_id=property_id,
            name=f"Email Import: {property_name[:100]}",
            stage=DealStage.INTAKE.value,
            source="email_import",
            notes=f"Auto-imported from Gmail message {message_id}",
        )
        db.add(new_deal)

        # Create ParsedDocument records for each saved attachment
        for file_path in attachments_saved:
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            mime = "application/pdf" if filename.lower().endswith(".pdf") else "image/jpeg"

            doc = ParsedDocument(
                id=str(uuid.uuid4()),
                user_id=user_id,
                property_id=property_id,
                filename=filename,
                file_path=file_path,
                file_size=file_size,
                mime_type=mime,
                document_type=DocumentType.LEASING_FLYER.value,
                status=DocumentStatus.PENDING.value,
            )
            db.add(doc)

        try:
            await db.commit()
            logger.info(
                "[gmail_monitor] Processed email %s -> property=%s, deal=%s, %d attachments",
                message_id,
                property_id,
                deal_id,
                len(attachments_saved),
            )
        except Exception as e:
            await db.rollback()
            error_msg = f"Database error: {e}"
            logger.error("[gmail_monitor] %s", error_msg)
            errors.append(error_msg)
            return {
                "property_id": None,
                "deal_id": None,
                "attachments_saved": [],
                "subject": subject,
                "errors": errors,
            }

        return {
            "property_id": property_id,
            "deal_id": deal_id,
            "attachments_saved": attachments_saved,
            "subject": subject,
            "errors": errors if errors else None,
        }
