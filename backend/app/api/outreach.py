"""
Outreach API Endpoints

Handles email outreach campaigns for tenant prospecting based on void analysis.
This is the "game changer" feature that automates the manual spreadsheet + mail merge workflow.
"""

from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.db.models.outreach import (
    OutreachCampaign,
    OutreachRecipient,
    OutreachTemplate,
    CampaignStatus,
    RecipientStatus,
)
from app.services.email_blast import (
    send_campaign_emails,
    generate_default_subject,
    generate_default_body,
    generate_void_outreach_body,
)
from app.services.placer import get_void_opportunities_structured


router = APIRouter(prefix="/outreach", tags=["outreach"])


# ============= Pydantic Models =============

class RecipientCreate(BaseModel):
    tenant_name: str
    contact_email: EmailStr
    contact_name: str | None = None
    contact_title: str | None = None
    category: str | None = None
    match_score: float | None = None
    nearest_location: str | None = None
    distance_miles: float | None = None


class CampaignCreate(BaseModel):
    name: str
    property_address: str
    property_name: str | None = None
    subject: str
    body_template: str
    from_name: str
    from_email: EmailStr
    reply_to: EmailStr | None = None
    recipients: list[RecipientCreate]


class CampaignUpdate(BaseModel):
    name: str | None = None
    subject: str | None = None
    body_template: str | None = None
    from_name: str | None = None
    from_email: EmailStr | None = None
    reply_to: EmailStr | None = None


class RecipientResponse(BaseModel):
    id: str
    tenant_name: str
    contact_email: str
    contact_name: str | None
    category: str | None
    match_score: float | None
    nearest_location: str | None
    distance_miles: float | None
    status: str
    is_excluded: bool
    sent_at: datetime | None
    opened_at: datetime | None
    replied_at: datetime | None

    class Config:
        from_attributes = True


class CampaignResponse(BaseModel):
    id: str
    name: str
    property_address: str
    property_name: str | None
    subject: str
    body_template: str
    from_name: str
    from_email: str
    reply_to: str | None
    status: str
    created_at: datetime
    sent_at: datetime | None
    total_recipients: int
    sent_count: int
    opened_count: int
    replied_count: int
    bounced_count: int
    recipients: list[RecipientResponse] | None = None

    class Config:
        from_attributes = True


class CampaignListResponse(BaseModel):
    id: str
    name: str
    property_name: str | None
    status: str
    created_at: datetime
    sent_at: datetime | None
    total_recipients: int
    sent_count: int
    opened_count: int
    replied_count: int

    class Config:
        from_attributes = True


class VoidOpportunityResponse(BaseModel):
    tenant_name: str
    category: str
    contact_email: str | None
    nearest_location: str | None
    distance_miles: float | None
    match_score: float


class SendCampaignResponse(BaseModel):
    success: bool
    message: str
    total_sent: int
    total_failed: int


class TemplateCreate(BaseModel):
    name: str
    description: str | None = None
    subject_template: str
    body_template: str
    category: str | None = None


class TemplateResponse(BaseModel):
    id: str
    name: str
    description: str | None
    subject_template: str
    body_template: str
    category: str | None
    times_used: int
    is_default: bool

    class Config:
        from_attributes = True


# ============= Endpoints =============

@router.get("/void-opportunities")
async def get_void_opportunities(
    address: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[VoidOpportunityResponse]:
    """
    Get void opportunities for a property address.

    Returns tenants that are missing from the market with contact info
    for use in outreach campaigns.
    """
    opportunities = await get_void_opportunities_structured(address)

    if not opportunities:
        return []

    return [
        VoidOpportunityResponse(
            tenant_name=opp["tenant_name"],
            category=opp["category"],
            contact_email=opp.get("contact_email"),
            nearest_location=opp.get("nearest_location"),
            distance_miles=opp.get("distance_miles"),
            match_score=opp.get("match_score", 0),
        )
        for opp in opportunities
    ]


@router.post("/campaigns", response_model=CampaignResponse)
async def create_campaign(
    campaign: CampaignCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignResponse:
    """
    Create a new outreach campaign.

    Typically created after running void analysis and selecting target tenants.
    """
    # Create campaign
    db_campaign = OutreachCampaign(
        user_id=current_user.id,
        name=campaign.name,
        property_address=campaign.property_address,
        property_name=campaign.property_name,
        subject=campaign.subject,
        body_template=campaign.body_template,
        from_name=campaign.from_name,
        from_email=campaign.from_email,
        reply_to=campaign.reply_to,
        status=CampaignStatus.DRAFT.value,
        total_recipients=len(campaign.recipients),
    )
    db.add(db_campaign)
    await db.flush()  # Get the campaign ID

    # Create recipients
    for recipient in campaign.recipients:
        db_recipient = OutreachRecipient(
            campaign_id=db_campaign.id,
            tenant_name=recipient.tenant_name,
            contact_email=recipient.contact_email,
            contact_name=recipient.contact_name,
            contact_title=recipient.contact_title,
            category=recipient.category,
            match_score=recipient.match_score,
            nearest_location=recipient.nearest_location,
            distance_miles=recipient.distance_miles,
        )
        db.add(db_recipient)

    await db.commit()
    await db.refresh(db_campaign)

    # Load recipients for response
    result = await db.execute(
        select(OutreachCampaign)
        .options(selectinload(OutreachCampaign.recipients))
        .where(OutreachCampaign.id == db_campaign.id)
    )
    db_campaign = result.scalar_one()

    return CampaignResponse(
        id=db_campaign.id,
        name=db_campaign.name,
        property_address=db_campaign.property_address,
        property_name=db_campaign.property_name,
        subject=db_campaign.subject,
        body_template=db_campaign.body_template,
        from_name=db_campaign.from_name,
        from_email=db_campaign.from_email,
        reply_to=db_campaign.reply_to,
        status=db_campaign.status,
        created_at=db_campaign.created_at,
        sent_at=db_campaign.sent_at,
        total_recipients=db_campaign.total_recipients,
        sent_count=db_campaign.sent_count,
        opened_count=db_campaign.opened_count,
        replied_count=db_campaign.replied_count,
        bounced_count=db_campaign.bounced_count,
        recipients=[
            RecipientResponse(
                id=r.id,
                tenant_name=r.tenant_name,
                contact_email=r.contact_email,
                contact_name=r.contact_name,
                category=r.category,
                match_score=r.match_score,
                nearest_location=r.nearest_location,
                distance_miles=r.distance_miles,
                status=r.status,
                is_excluded=r.is_excluded,
                sent_at=r.sent_at,
                opened_at=r.opened_at,
                replied_at=r.replied_at,
            )
            for r in db_campaign.recipients
        ],
    )


@router.get("/campaigns", response_model=list[CampaignListResponse])
async def list_campaigns(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CampaignListResponse]:
    """List all campaigns for the current user."""
    result = await db.execute(
        select(OutreachCampaign)
        .where(OutreachCampaign.user_id == current_user.id)
        .order_by(OutreachCampaign.created_at.desc())
    )
    campaigns = result.scalars().all()

    return [
        CampaignListResponse(
            id=c.id,
            name=c.name,
            property_name=c.property_name,
            status=c.status,
            created_at=c.created_at,
            sent_at=c.sent_at,
            total_recipients=c.total_recipients,
            sent_count=c.sent_count,
            opened_count=c.opened_count,
            replied_count=c.replied_count,
        )
        for c in campaigns
    ]


@router.get("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignResponse:
    """Get a campaign with all recipients."""
    result = await db.execute(
        select(OutreachCampaign)
        .options(selectinload(OutreachCampaign.recipients))
        .where(
            OutreachCampaign.id == campaign_id,
            OutreachCampaign.user_id == current_user.id,
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        property_address=campaign.property_address,
        property_name=campaign.property_name,
        subject=campaign.subject,
        body_template=campaign.body_template,
        from_name=campaign.from_name,
        from_email=campaign.from_email,
        reply_to=campaign.reply_to,
        status=campaign.status,
        created_at=campaign.created_at,
        sent_at=campaign.sent_at,
        total_recipients=campaign.total_recipients,
        sent_count=campaign.sent_count,
        opened_count=campaign.opened_count,
        replied_count=campaign.replied_count,
        bounced_count=campaign.bounced_count,
        recipients=[
            RecipientResponse(
                id=r.id,
                tenant_name=r.tenant_name,
                contact_email=r.contact_email,
                contact_name=r.contact_name,
                category=r.category,
                match_score=r.match_score,
                nearest_location=r.nearest_location,
                distance_miles=r.distance_miles,
                status=r.status,
                is_excluded=r.is_excluded,
                sent_at=r.sent_at,
                opened_at=r.opened_at,
                replied_at=r.replied_at,
            )
            for r in campaign.recipients
        ],
    )


@router.patch("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: str,
    updates: CampaignUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignResponse:
    """Update a draft campaign."""
    result = await db.execute(
        select(OutreachCampaign)
        .options(selectinload(OutreachCampaign.recipients))
        .where(
            OutreachCampaign.id == campaign_id,
            OutreachCampaign.user_id == current_user.id,
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status != CampaignStatus.DRAFT.value:
        raise HTTPException(
            status_code=400,
            detail="Can only update draft campaigns"
        )

    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(campaign, field, value)

    campaign.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(campaign)

    return await get_campaign(campaign_id, current_user, db)


@router.post("/campaigns/{campaign_id}/exclude/{recipient_id}")
async def exclude_recipient(
    campaign_id: str,
    recipient_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Exclude a recipient from a campaign."""
    result = await db.execute(
        select(OutreachRecipient)
        .join(OutreachCampaign)
        .where(
            OutreachRecipient.id == recipient_id,
            OutreachCampaign.id == campaign_id,
            OutreachCampaign.user_id == current_user.id,
        )
    )
    recipient = result.scalar_one_or_none()

    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")

    recipient.is_excluded = True
    await db.commit()

    return {"success": True, "message": f"Excluded {recipient.tenant_name}"}


@router.post("/campaigns/{campaign_id}/include/{recipient_id}")
async def include_recipient(
    campaign_id: str,
    recipient_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Re-include an excluded recipient."""
    result = await db.execute(
        select(OutreachRecipient)
        .join(OutreachCampaign)
        .where(
            OutreachRecipient.id == recipient_id,
            OutreachCampaign.id == campaign_id,
            OutreachCampaign.user_id == current_user.id,
        )
    )
    recipient = result.scalar_one_or_none()

    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")

    recipient.is_excluded = False
    await db.commit()

    return {"success": True, "message": f"Included {recipient.tenant_name}"}


@router.post("/campaigns/{campaign_id}/send", response_model=SendCampaignResponse)
async def send_campaign(
    campaign_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SendCampaignResponse:
    """
    Send a campaign to all non-excluded recipients.

    This is the moment of truth - actually sending emails to hundreds of tenants!
    """
    result = await db.execute(
        select(OutreachCampaign)
        .options(selectinload(OutreachCampaign.recipients))
        .where(
            OutreachCampaign.id == campaign_id,
            OutreachCampaign.user_id == current_user.id,
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status not in [CampaignStatus.DRAFT.value, CampaignStatus.SCHEDULED.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Campaign already {campaign.status}"
        )

    # Get non-excluded, pending recipients
    recipients_to_send = [
        r for r in campaign.recipients
        if not r.is_excluded and r.status == RecipientStatus.PENDING.value
    ]

    if not recipients_to_send:
        raise HTTPException(
            status_code=400,
            detail="No recipients to send to"
        )

    # Update campaign status
    campaign.status = CampaignStatus.SENDING.value
    campaign.sent_at = datetime.utcnow()
    await db.commit()

    # Prepare recipients data
    recipients_data = [
        {
            "tenant_name": r.tenant_name,
            "contact_email": r.contact_email,
        }
        for r in recipients_to_send
    ]

    # Send emails
    summary = await send_campaign_emails(
        recipients=recipients_data,
        subject_template=campaign.subject,
        body_template=campaign.body_template,
        property_name=campaign.property_name or campaign.property_address,
        property_address=campaign.property_address,
        from_name=campaign.from_name,
        from_email=campaign.from_email,
        reply_to=campaign.reply_to,
    )

    # Update recipient statuses
    for result in summary.results:
        for recipient in recipients_to_send:
            if recipient.contact_email == result.recipient_email:
                if result.success:
                    recipient.status = RecipientStatus.SENT.value
                    recipient.sent_at = result.sent_at
                else:
                    recipient.status = RecipientStatus.BOUNCED.value
                    recipient.error_message = result.error
                break

    # Update campaign stats
    campaign.sent_count = summary.successful
    campaign.bounced_count = summary.failed
    campaign.status = CampaignStatus.SENT.value
    campaign.completed_at = datetime.utcnow()

    await db.commit()

    return SendCampaignResponse(
        success=summary.successful > 0,
        message=f"Sent {summary.successful} emails, {summary.failed} failed",
        total_sent=summary.successful,
        total_failed=summary.failed,
    )


@router.delete("/campaigns/{campaign_id}")
async def delete_campaign(
    campaign_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Delete a campaign (only drafts can be deleted)."""
    result = await db.execute(
        select(OutreachCampaign)
        .where(
            OutreachCampaign.id == campaign_id,
            OutreachCampaign.user_id == current_user.id,
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status != CampaignStatus.DRAFT.value:
        raise HTTPException(
            status_code=400,
            detail="Can only delete draft campaigns"
        )

    await db.delete(campaign)
    await db.commit()

    return {"success": True, "message": "Campaign deleted"}


# ============= Templates =============

@router.get("/templates", response_model=list[TemplateResponse])
async def list_templates(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TemplateResponse]:
    """List all email templates for the user."""
    result = await db.execute(
        select(OutreachTemplate)
        .where(OutreachTemplate.user_id == current_user.id)
        .order_by(OutreachTemplate.is_default.desc(), OutreachTemplate.times_used.desc())
    )
    templates = result.scalars().all()

    return [
        TemplateResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            subject_template=t.subject_template,
            body_template=t.body_template,
            category=t.category,
            times_used=t.times_used,
            is_default=t.is_default,
        )
        for t in templates
    ]


@router.post("/templates", response_model=TemplateResponse)
async def create_template(
    template: TemplateCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TemplateResponse:
    """Create a new email template."""
    db_template = OutreachTemplate(
        user_id=current_user.id,
        name=template.name,
        description=template.description,
        subject_template=template.subject_template,
        body_template=template.body_template,
        category=template.category,
    )
    db.add(db_template)
    await db.commit()
    await db.refresh(db_template)

    return TemplateResponse(
        id=db_template.id,
        name=db_template.name,
        description=db_template.description,
        subject_template=db_template.subject_template,
        body_template=db_template.body_template,
        category=db_template.category,
        times_used=db_template.times_used,
        is_default=db_template.is_default,
    )


@router.get("/templates/defaults")
async def get_default_templates() -> dict:
    """Get default email templates for quick start."""
    return {
        "standard": {
            "name": "Standard Outreach",
            "subject": "Retail Opportunity at {{property_name}}",
            "body": generate_default_body(),
        },
        "void_analysis": {
            "name": "Void Analysis Outreach",
            "subject": "Market Opportunity for {{tenant_name}} at {{property_name}}",
            "body": generate_void_outreach_body(),
        },
    }
