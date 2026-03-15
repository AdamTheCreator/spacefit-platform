"""
Reports API — Export analysis results as PDF, CSV, or shareable links.
"""

import csv
import io
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db
from app.db.models.chat import ChatMessage, ChatSession
from app.db.models.report import SharedReport
from app.services.report_generator import generate_session_report

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])


class GenerateReportRequest(BaseModel):
    session_id: str
    report_type: str = "comprehensive"  # demographics, tenant_mix, comprehensive


class ShareLinkResponse(BaseModel):
    share_url: str
    expires_at: datetime
    share_token: str


class ReportResponse(BaseModel):
    id: str
    share_token: str
    report_type: str
    title: str | None
    view_count: int
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# ── PDF Export ──────────────────────────────────────────────────────

@router.post("/generate/pdf")
async def generate_pdf_report(
    body: GenerateReportRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Generate a branded PDF report from a chat session's analysis results."""
    session, messages = await _get_session_messages(body.session_id, current_user.id, db)

    # Extract agent messages content for the report
    content_sections = _extract_report_sections(messages, body.report_type)
    if not content_sections:
        raise HTTPException(status_code=404, detail="No analysis data found in this session")

    pdf_bytes = generate_session_report(
        title=session.title or "Analysis Report",
        sections=content_sections,
        report_type=body.report_type,
    )

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="report-{session.id[:8]}.pdf"',
        },
    )


# ── CSV Export ──────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/csv")
async def export_session_csv(
    session_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    report_type: str = "comprehensive",
):
    """Export analysis data as CSV."""
    _, messages = await _get_session_messages(session_id, current_user.id, db)

    rows = _extract_csv_rows(messages, report_type)
    if not rows:
        raise HTTPException(status_code=404, detail="No exportable data found")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="data-{session_id[:8]}.csv"',
        },
    )


# ── Shareable Link ──────────────────────────────────────────────────

@router.post("/share", response_model=ShareLinkResponse)
async def create_share_link(
    body: GenerateReportRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Create a shareable link for an analysis report."""
    session, messages = await _get_session_messages(body.session_id, current_user.id, db)

    # Build content snapshot from visible agent messages
    content_parts = []
    for msg in messages:
        if msg.role == "agent" and msg.visible:
            content_parts.append(msg.content)

    content_snapshot = "\n\n---\n\n".join(content_parts) if content_parts else ""

    report = SharedReport(
        session_id=body.session_id,
        user_id=current_user.id,
        report_type=body.report_type,
        title=session.title,
        content_snapshot=content_snapshot,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    # Build the share URL — frontend will handle the rendering
    share_url = f"/shared/report/{report.share_token}"

    return ShareLinkResponse(
        share_url=share_url,
        expires_at=report.expires_at,
        share_token=report.share_token,
    )


@router.get("/shared/{share_token}")
async def get_shared_report(
    share_token: str,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint — view a shared report (no auth required)."""
    result = await db.execute(
        select(SharedReport).where(SharedReport.share_token == share_token)
    )
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if report.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="This report has expired")

    # Increment view count
    report.view_count += 1
    await db.commit()

    return {
        "title": report.title,
        "report_type": report.report_type,
        "content": report.content_snapshot,
        "created_at": report.created_at.isoformat(),
        "expires_at": report.expires_at.isoformat(),
    }


# ── Helpers ─────────────────────────────────────────────────────────

async def _get_session_messages(
    session_id: str, user_id: str, db: AsyncSession
) -> tuple[ChatSession, list[ChatMessage]]:
    """Load a session and its messages, verifying ownership."""
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == user_id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = list(result.scalars().all())
    return session, messages


def _extract_report_sections(
    messages: list[ChatMessage], report_type: str
) -> list[dict[str, str]]:
    """Extract structured sections from agent messages for PDF generation."""
    sections = []
    for msg in messages:
        if msg.role != "agent" or not msg.visible:
            continue
        # Use agent_type as section type
        sections.append({
            "type": msg.agent_type or "analysis",
            "content": msg.content,
        })
    return sections


def _extract_csv_rows(
    messages: list[ChatMessage], report_type: str
) -> list[dict[str, str]]:
    """Extract tabular data from agent messages for CSV export."""
    rows = []
    for msg in messages:
        if msg.role != "agent" or not msg.visible:
            continue
        # Parse markdown tables and bullet points into rows
        for line in msg.content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("---"):
                continue
            # Bullet point data
            if line.startswith("- ") or line.startswith("* "):
                content = line[2:].strip()
                if ":" in content:
                    key, value = content.split(":", 1)
                    rows.append({
                        "section": msg.agent_type or "analysis",
                        "metric": key.strip().strip("*"),
                        "value": value.strip(),
                    })
    return rows
