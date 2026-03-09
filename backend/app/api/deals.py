from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, CurrentUser
from app.db.models.deal import Deal, DealStageHistory, DealActivity, Property
from app.db.models.deal import DealStage as DealStageEnum
from app.models.deal import (
    DealCreate,
    DealUpdate,
    DealResponse,
    DealDetailResponse,
    DealListResponse,
    DealStageUpdate,
    DealActivityCreate,
    DealActivityResponse,
    DealStageHistoryResponse,
    PipelineSummary,
    StageSummary,
    CommissionForecast,
    MonthlyForecast,
    DealCalendarItem,
    PropertyCreate,
    PropertyUpdate,
    PropertyResponse,
    DealStage,
)

router = APIRouter(prefix="/deals", tags=["deals"])


# ============ DEAL ENDPOINTS ============

@router.get("", response_model=DealListResponse)
async def list_deals(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    stage: DealStage | None = None,
    search: str | None = None,
    is_archived: bool = False,
) -> DealListResponse:
    """List deals with pagination and optional filtering."""
    query = select(Deal).where(
        Deal.user_id == current_user.id,
        Deal.is_archived == is_archived,
    )

    if stage:
        query = query.where(Deal.stage == stage.value)

    if search:
        search_filter = f"%{search}%"
        query = query.where(Deal.name.ilike(search_filter))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get deals with relationships
    query = (
        query.options(selectinload(Deal.property), selectinload(Deal.customer))
        .order_by(Deal.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    deals = result.scalars().all()

    pages = (total + page_size - 1) // page_size

    # Map to response with customer name
    items = []
    for deal in deals:
        deal_dict = {
            "id": deal.id,
            "user_id": deal.user_id,
            "name": deal.name,
            "stage": deal.stage,
            "deal_type": deal.deal_type,
            "property_id": deal.property_id,
            "customer_id": deal.customer_id,
            "asking_rent_psf": deal.asking_rent_psf,
            "negotiated_rent_psf": deal.negotiated_rent_psf,
            "square_footage": deal.square_footage,
            "commission_rate": deal.commission_rate,
            "commission_amount": deal.commission_amount,
            "probability": deal.probability,
            "expected_close_date": deal.expected_close_date,
            "actual_close_date": deal.actual_close_date,
            "lease_start_date": deal.lease_start_date,
            "lease_term_months": deal.lease_term_months,
            "source": deal.source,
            "notes": deal.notes,
            "is_archived": deal.is_archived,
            "created_at": deal.created_at,
            "updated_at": deal.updated_at,
            "property": deal.property,
            "customer_name": deal.customer.name if deal.customer else None,
        }
        items.append(DealResponse(**deal_dict))

    return DealListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("", response_model=DealResponse, status_code=status.HTTP_201_CREATED)
async def create_deal(
    deal_data: DealCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DealResponse:
    """Create a new deal."""
    deal = Deal(
        user_id=current_user.id,
        name=deal_data.name,
        stage=deal_data.stage.value,
        deal_type=deal_data.deal_type.value,
        property_id=deal_data.property_id,
        customer_id=deal_data.customer_id,
        asking_rent_psf=deal_data.asking_rent_psf,
        negotiated_rent_psf=deal_data.negotiated_rent_psf,
        square_footage=deal_data.square_footage,
        commission_rate=deal_data.commission_rate,
        commission_amount=deal_data.commission_amount,
        probability=deal_data.probability,
        expected_close_date=deal_data.expected_close_date,
        actual_close_date=deal_data.actual_close_date,
        lease_start_date=deal_data.lease_start_date,
        lease_term_months=deal_data.lease_term_months,
        source=deal_data.source,
        notes=deal_data.notes,
    )

    # Create initial stage history
    stage_history = DealStageHistory(
        deal_id=deal.id,
        from_stage=None,
        to_stage=deal_data.stage.value,
        changed_by=current_user.id,
    )
    deal.stage_history.append(stage_history)

    db.add(deal)
    await db.commit()
    await db.refresh(deal)

    # Load relationships
    result = await db.execute(
        select(Deal)
        .options(selectinload(Deal.property), selectinload(Deal.customer))
        .where(Deal.id == deal.id)
    )
    deal = result.scalar_one()

    return DealResponse(
        id=deal.id,
        user_id=deal.user_id,
        name=deal.name,
        stage=deal.stage,
        deal_type=deal.deal_type,
        property_id=deal.property_id,
        customer_id=deal.customer_id,
        asking_rent_psf=deal.asking_rent_psf,
        negotiated_rent_psf=deal.negotiated_rent_psf,
        square_footage=deal.square_footage,
        commission_rate=deal.commission_rate,
        commission_amount=deal.commission_amount,
        probability=deal.probability,
        expected_close_date=deal.expected_close_date,
        actual_close_date=deal.actual_close_date,
        lease_start_date=deal.lease_start_date,
        lease_term_months=deal.lease_term_months,
        source=deal.source,
        notes=deal.notes,
        is_archived=deal.is_archived,
        created_at=deal.created_at,
        updated_at=deal.updated_at,
        property=deal.property,
        customer_name=deal.customer.name if deal.customer else None,
    )


@router.get("/pipeline", response_model=PipelineSummary)
async def get_pipeline_summary(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PipelineSummary:
    """Get pipeline summary with counts and totals by stage."""
    query = (
        select(
            Deal.stage,
            func.count(Deal.id).label("count"),
            func.coalesce(func.sum(Deal.commission_amount), 0).label("total_commission"),
        )
        .where(Deal.user_id == current_user.id, Deal.is_archived == False)
        .group_by(Deal.stage)
    )

    result = await db.execute(query)
    rows = result.all()

    # Build stage summaries for all stages (even if empty)
    stage_data = {row.stage: {"count": row.count, "total_commission": float(row.total_commission)} for row in rows}

    stages = []
    total_deals = 0
    total_commission = 0.0

    for stage in DealStage:
        data = stage_data.get(stage.value, {"count": 0, "total_commission": 0.0})
        stages.append(StageSummary(
            stage=stage,
            count=data["count"],
            total_commission=data["total_commission"],
        ))
        total_deals += data["count"]
        total_commission += data["total_commission"]

    return PipelineSummary(
        stages=stages,
        total_deals=total_deals,
        total_potential_commission=total_commission,
    )


@router.get("/forecast", response_model=CommissionForecast)
async def get_commission_forecast(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    months: int = Query(6, ge=1, le=24),
) -> CommissionForecast:
    """Get commission forecast for upcoming months."""
    from datetime import datetime
    from dateutil.relativedelta import relativedelta

    today = date.today()
    end_date = today + relativedelta(months=months)

    # Get deals with expected close dates in the forecast period
    query = (
        select(Deal)
        .where(
            Deal.user_id == current_user.id,
            Deal.is_archived == False,
            Deal.expected_close_date >= today,
            Deal.expected_close_date <= end_date,
            Deal.stage.notin_([DealStageEnum.CLOSED.value, DealStageEnum.PASSED.value, DealStageEnum.DEAD.value]),
        )
    )

    result = await db.execute(query)
    deals = result.scalars().all()

    # Group by month
    monthly_data: dict[str, dict] = {}
    for i in range(months):
        month_date = today + relativedelta(months=i)
        month_key = month_date.strftime("%Y-%m")
        monthly_data[month_key] = {"expected_commission": 0.0, "deal_count": 0}

    for deal in deals:
        if deal.expected_close_date:
            month_key = deal.expected_close_date.strftime("%Y-%m")
            if month_key in monthly_data:
                # Weight by probability
                commission = (deal.commission_amount or 0) * (deal.probability / 100)
                monthly_data[month_key]["expected_commission"] += commission
                monthly_data[month_key]["deal_count"] += 1

    forecast = [
        MonthlyForecast(
            month=month,
            expected_commission=data["expected_commission"],
            deal_count=data["deal_count"],
        )
        for month, data in sorted(monthly_data.items())
    ]

    total_forecast = sum(f.expected_commission for f in forecast)

    return CommissionForecast(forecast=forecast, total_forecast=total_forecast)


@router.get("/calendar", response_model=list[DealCalendarItem])
async def get_deals_calendar(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[DealCalendarItem]:
    """Get deals for calendar view with relevant dates."""
    from datetime import timedelta

    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today() + timedelta(days=90)

    query = (
        select(Deal)
        .where(
            Deal.user_id == current_user.id,
            Deal.is_archived == False,
        )
    )

    result = await db.execute(query)
    deals = result.scalars().all()

    calendar_items = []
    for deal in deals:
        # Add expected close date
        if deal.expected_close_date and start_date <= deal.expected_close_date <= end_date:
            calendar_items.append(DealCalendarItem(
                id=deal.id,
                name=deal.name,
                stage=deal.stage,
                date=deal.expected_close_date,
                date_type="expected_close",
                commission_amount=deal.commission_amount,
            ))
        # Add lease start date
        if deal.lease_start_date and start_date <= deal.lease_start_date <= end_date:
            calendar_items.append(DealCalendarItem(
                id=deal.id,
                name=deal.name,
                stage=deal.stage,
                date=deal.lease_start_date,
                date_type="lease_start",
                commission_amount=deal.commission_amount,
            ))
        # Add actual close date
        if deal.actual_close_date and start_date <= deal.actual_close_date <= end_date:
            calendar_items.append(DealCalendarItem(
                id=deal.id,
                name=deal.name,
                stage=deal.stage,
                date=deal.actual_close_date,
                date_type="actual_close",
                commission_amount=deal.commission_amount,
            ))

    return sorted(calendar_items, key=lambda x: x.date)


@router.get("/{deal_id}", response_model=DealDetailResponse)
async def get_deal(
    deal_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DealDetailResponse:
    """Get a deal by ID with full details."""
    result = await db.execute(
        select(Deal)
        .options(
            selectinload(Deal.property),
            selectinload(Deal.customer),
            selectinload(Deal.stage_history),
            selectinload(Deal.activities),
        )
        .where(Deal.id == str(deal_id), Deal.user_id == current_user.id)
    )
    deal = result.scalar_one_or_none()

    if deal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deal not found",
        )

    return DealDetailResponse(
        id=deal.id,
        user_id=deal.user_id,
        name=deal.name,
        stage=deal.stage,
        deal_type=deal.deal_type,
        property_id=deal.property_id,
        customer_id=deal.customer_id,
        asking_rent_psf=deal.asking_rent_psf,
        negotiated_rent_psf=deal.negotiated_rent_psf,
        square_footage=deal.square_footage,
        commission_rate=deal.commission_rate,
        commission_amount=deal.commission_amount,
        probability=deal.probability,
        expected_close_date=deal.expected_close_date,
        actual_close_date=deal.actual_close_date,
        lease_start_date=deal.lease_start_date,
        lease_term_months=deal.lease_term_months,
        source=deal.source,
        notes=deal.notes,
        is_archived=deal.is_archived,
        created_at=deal.created_at,
        updated_at=deal.updated_at,
        property=deal.property,
        customer_name=deal.customer.name if deal.customer else None,
        stage_history=[DealStageHistoryResponse.model_validate(h) for h in deal.stage_history],
        activities=[DealActivityResponse.model_validate(a) for a in deal.activities],
    )


@router.put("/{deal_id}", response_model=DealResponse)
async def update_deal(
    deal_id: UUID,
    deal_data: DealUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DealResponse:
    """Update a deal."""
    result = await db.execute(
        select(Deal)
        .options(selectinload(Deal.property), selectinload(Deal.customer))
        .where(Deal.id == str(deal_id), Deal.user_id == current_user.id)
    )
    deal = result.scalar_one_or_none()

    if deal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deal not found",
        )

    update_data = deal_data.model_dump(exclude_unset=True)

    # Handle stage change with history
    if "stage" in update_data and update_data["stage"] != deal.stage:
        stage_history = DealStageHistory(
            deal_id=deal.id,
            from_stage=deal.stage,
            to_stage=update_data["stage"].value if hasattr(update_data["stage"], "value") else update_data["stage"],
            changed_by=current_user.id,
        )
        db.add(stage_history)
        update_data["stage"] = update_data["stage"].value if hasattr(update_data["stage"], "value") else update_data["stage"]

    # Convert enums to values
    if "deal_type" in update_data and hasattr(update_data["deal_type"], "value"):
        update_data["deal_type"] = update_data["deal_type"].value

    for field, value in update_data.items():
        setattr(deal, field, value)

    await db.commit()
    await db.refresh(deal)

    return DealResponse(
        id=deal.id,
        user_id=deal.user_id,
        name=deal.name,
        stage=deal.stage,
        deal_type=deal.deal_type,
        property_id=deal.property_id,
        customer_id=deal.customer_id,
        asking_rent_psf=deal.asking_rent_psf,
        negotiated_rent_psf=deal.negotiated_rent_psf,
        square_footage=deal.square_footage,
        commission_rate=deal.commission_rate,
        commission_amount=deal.commission_amount,
        probability=deal.probability,
        expected_close_date=deal.expected_close_date,
        actual_close_date=deal.actual_close_date,
        lease_start_date=deal.lease_start_date,
        lease_term_months=deal.lease_term_months,
        source=deal.source,
        notes=deal.notes,
        is_archived=deal.is_archived,
        created_at=deal.created_at,
        updated_at=deal.updated_at,
        property=deal.property,
        customer_name=deal.customer.name if deal.customer else None,
    )


@router.patch("/{deal_id}/stage", response_model=DealResponse)
async def update_deal_stage(
    deal_id: UUID,
    stage_data: DealStageUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DealResponse:
    """Move deal to a new stage (with history tracking)."""
    result = await db.execute(
        select(Deal)
        .options(selectinload(Deal.property), selectinload(Deal.customer))
        .where(Deal.id == str(deal_id), Deal.user_id == current_user.id)
    )
    deal = result.scalar_one_or_none()

    if deal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deal not found",
        )

    old_stage = deal.stage
    new_stage = stage_data.stage.value

    if old_stage == new_stage:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deal is already in this stage",
        )

    # Create stage history
    stage_history = DealStageHistory(
        deal_id=deal.id,
        from_stage=old_stage,
        to_stage=new_stage,
        changed_by=current_user.id,
        notes=stage_data.notes,
    )
    db.add(stage_history)

    deal.stage = new_stage

    # If moving to closed, set actual close date
    if new_stage == DealStageEnum.CLOSED.value and not deal.actual_close_date:
        deal.actual_close_date = date.today()

    await db.commit()
    await db.refresh(deal)

    return DealResponse(
        id=deal.id,
        user_id=deal.user_id,
        name=deal.name,
        stage=deal.stage,
        deal_type=deal.deal_type,
        property_id=deal.property_id,
        customer_id=deal.customer_id,
        asking_rent_psf=deal.asking_rent_psf,
        negotiated_rent_psf=deal.negotiated_rent_psf,
        square_footage=deal.square_footage,
        commission_rate=deal.commission_rate,
        commission_amount=deal.commission_amount,
        probability=deal.probability,
        expected_close_date=deal.expected_close_date,
        actual_close_date=deal.actual_close_date,
        lease_start_date=deal.lease_start_date,
        lease_term_months=deal.lease_term_months,
        source=deal.source,
        notes=deal.notes,
        is_archived=deal.is_archived,
        created_at=deal.created_at,
        updated_at=deal.updated_at,
        property=deal.property,
        customer_name=deal.customer.name if deal.customer else None,
    )


@router.delete("/{deal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deal(
    deal_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a deal."""
    result = await db.execute(
        select(Deal).where(Deal.id == str(deal_id), Deal.user_id == current_user.id)
    )
    deal = result.scalar_one_or_none()

    if deal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deal not found",
        )

    await db.delete(deal)
    await db.commit()


# ============ DEAL ACTIVITIES ENDPOINTS ============

@router.get("/{deal_id}/activities", response_model=list[DealActivityResponse])
async def list_deal_activities(
    deal_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[DealActivityResponse]:
    """Get all activities for a deal."""
    # Verify deal belongs to user
    deal_result = await db.execute(
        select(Deal).where(Deal.id == str(deal_id), Deal.user_id == current_user.id)
    )
    if not deal_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    result = await db.execute(
        select(DealActivity)
        .where(DealActivity.deal_id == str(deal_id))
        .order_by(DealActivity.created_at.desc())
    )
    activities = result.scalars().all()

    return [DealActivityResponse.model_validate(a) for a in activities]


@router.post("/{deal_id}/activities", response_model=DealActivityResponse, status_code=status.HTTP_201_CREATED)
async def create_deal_activity(
    deal_id: UUID,
    activity_data: DealActivityCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DealActivityResponse:
    """Add an activity to a deal."""
    # Verify deal belongs to user
    deal_result = await db.execute(
        select(Deal).where(Deal.id == str(deal_id), Deal.user_id == current_user.id)
    )
    if not deal_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    activity = DealActivity(
        deal_id=str(deal_id),
        user_id=current_user.id,
        activity_type=activity_data.activity_type.value,
        title=activity_data.title,
        description=activity_data.description,
        scheduled_at=activity_data.scheduled_at,
        completed_at=activity_data.completed_at,
    )

    db.add(activity)
    await db.commit()
    await db.refresh(activity)

    return DealActivityResponse.model_validate(activity)


# ============ PROPERTIES ENDPOINTS ============

properties_router = APIRouter(prefix="/properties", tags=["properties"])


@properties_router.get("/comps", response_model=list[PropertyResponse])
async def list_comps(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    state: str | None = None,
    min_cap_rate: float | None = None,
    max_cap_rate: float | None = None,
) -> list[PropertyResponse]:
    """List sale comp properties."""
    query = select(Property).where(
        Property.user_id == current_user.id,
        Property.is_sale_comp == True,
    )

    if state:
        query = query.where(Property.state.ilike(f"%{state}%"))
    if min_cap_rate is not None:
        query = query.where(Property.cap_rate >= min_cap_rate)
    if max_cap_rate is not None:
        query = query.where(Property.cap_rate <= max_cap_rate)

    query = query.order_by(Property.updated_at.desc())
    result = await db.execute(query)
    properties = result.scalars().all()

    return [PropertyResponse.model_validate(p) for p in properties]


@properties_router.get("", response_model=list[PropertyResponse])
async def list_properties(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = None,
) -> list[PropertyResponse]:
    """List all properties for the user."""
    query = select(Property).where(Property.user_id == current_user.id)

    if search:
        search_filter = f"%{search}%"
        query = query.where(
            Property.name.ilike(search_filter) | Property.address.ilike(search_filter)
        )

    query = query.order_by(Property.name)
    result = await db.execute(query)
    properties = result.scalars().all()

    return [PropertyResponse.model_validate(p) for p in properties]


@properties_router.post("", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    property_data: PropertyCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PropertyResponse:
    """Create a new property."""
    prop = Property(
        user_id=current_user.id,
        name=property_data.name,
        address=property_data.address,
        city=property_data.city,
        state=property_data.state,
        zip_code=property_data.zip_code,
        latitude=property_data.latitude,
        longitude=property_data.longitude,
        property_type=property_data.property_type,
        total_sf=property_data.total_sf,
        available_sf=property_data.available_sf,
        landlord_id=property_data.landlord_id,
        notes=property_data.notes,
    )

    db.add(prop)
    await db.commit()
    await db.refresh(prop)

    return PropertyResponse.model_validate(prop)


@properties_router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PropertyResponse:
    """Get a property by ID."""
    result = await db.execute(
        select(Property).where(
            Property.id == str(property_id), Property.user_id == current_user.id
        )
    )
    prop = result.scalar_one_or_none()

    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    return PropertyResponse.model_validate(prop)


@properties_router.put("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: UUID,
    property_data: PropertyUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PropertyResponse:
    """Update a property."""
    result = await db.execute(
        select(Property).where(
            Property.id == str(property_id), Property.user_id == current_user.id
        )
    )
    prop = result.scalar_one_or_none()

    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    update_data = property_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(prop, field, value)

    await db.commit()
    await db.refresh(prop)

    return PropertyResponse.model_validate(prop)


@properties_router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(
    property_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a property."""
    result = await db.execute(
        select(Property).where(
            Property.id == str(property_id), Property.user_id == current_user.id
        )
    )
    prop = result.scalar_one_or_none()

    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    await db.delete(prop)
    await db.commit()


@properties_router.post("/{property_id}/qualify")
async def qualify_property(
    property_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Run qualification scoring on a property."""
    from app.services.qualification import score_property
    from app.services.market_config import MarketConfig
    from app.db.models.credential import UserPreferences

    # Get user's market config
    prefs_result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    prefs = prefs_result.scalar_one_or_none()
    config_data = getattr(prefs, 'market_config', None) if prefs else None
    market_config = MarketConfig.from_dict(config_data)

    try:
        score = await score_property(str(property_id), db, market_config)
        return score.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@properties_router.post("/{property_id}/mark-as-comp", response_model=PropertyResponse)
async def mark_as_comp(
    property_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PropertyResponse:
    """Mark a property as a sale comp."""
    result = await db.execute(
        select(Property).where(
            Property.id == str(property_id), Property.user_id == current_user.id
        )
    )
    prop = result.scalar_one_or_none()

    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    prop.is_sale_comp = True
    await db.commit()
    await db.refresh(prop)

    return PropertyResponse.model_validate(prop)


@properties_router.post("/import/csv")
async def import_csv(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
) -> dict:
    """Import properties from a CSV file (Airtable migration)."""
    from app.services.csv_import import import_properties_from_csv

    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV",
        )

    content = await file.read()
    result = await import_properties_from_csv(content, current_user.id, db)

    return {
        "total_rows": result.total_rows,
        "imported": result.imported,
        "skipped": result.skipped,
        "errors": result.errors,
    }


# ============ APPROVAL ENDPOINTS ============

approvals_router = APIRouter(prefix="/approvals", tags=["approvals"])


@approvals_router.get("")
async def list_approvals(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = None,
) -> list[dict]:
    """List approval requests."""
    from app.db.models.approval import ApprovalRequest

    query = select(ApprovalRequest).where(
        ApprovalRequest.requested_by == current_user.id
    )
    if status_filter:
        query = query.where(ApprovalRequest.status == status_filter)

    query = query.order_by(ApprovalRequest.created_at.desc())
    result = await db.execute(query)
    approvals = result.scalars().all()

    return [
        {
            "id": a.id,
            "deal_id": a.deal_id,
            "requested_by": a.requested_by,
            "approval_type": a.approval_type,
            "status": a.status,
            "decided_by": a.decided_by,
            "notes": a.notes,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "decided_at": a.decided_at.isoformat() if a.decided_at else None,
        }
        for a in approvals
    ]


@router.post("/{deal_id}/request-approval")
async def request_approval(
    deal_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    approval_type: str = "deal_advancement",
    notes: str | None = None,
) -> dict:
    """Request approval for a deal action."""
    from app.db.models.approval import ApprovalRequest

    # Verify deal exists and belongs to user
    deal_result = await db.execute(
        select(Deal).where(Deal.id == str(deal_id), Deal.user_id == current_user.id)
    )
    if not deal_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    approval = ApprovalRequest(
        deal_id=str(deal_id),
        requested_by=current_user.id,
        approval_type=approval_type,
        notes=notes,
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)

    return {
        "id": approval.id,
        "deal_id": approval.deal_id,
        "approval_type": approval.approval_type,
        "status": approval.status,
        "created_at": approval.created_at.isoformat(),
    }


@approvals_router.patch("/{approval_id}/decide")
async def decide_approval(
    approval_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    decision: str = "approved",  # "approved" or "rejected"
    notes: str | None = None,
) -> dict:
    """Approve or reject an approval request."""
    from datetime import datetime
    from app.db.models.approval import ApprovalRequest

    result = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.id == str(approval_id))
    )
    approval = result.scalar_one_or_none()

    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")

    if approval.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approval has already been decided",
        )

    approval.status = decision
    approval.decided_by = current_user.id
    approval.decided_at = datetime.utcnow()
    if notes:
        approval.notes = notes

    await db.commit()

    return {
        "id": approval.id,
        "status": approval.status,
        "decided_by": approval.decided_by,
        "decided_at": approval.decided_at.isoformat(),
    }


# ============ GMAIL MONITORING ENDPOINTS ============

@properties_router.post("/gmail/enable-monitoring")
async def enable_gmail_monitoring(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Enable Gmail inbox monitoring for property intake."""
    # Store monitoring preference in user preferences
    from app.db.models.credential import UserPreferences

    result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    prefs = result.scalar_one_or_none()
    if not prefs:
        prefs = UserPreferences(user_id=current_user.id)
        db.add(prefs)

    config = getattr(prefs, 'market_config', None) or {}
    config["gmail_monitoring_enabled"] = True
    prefs.market_config = config
    await db.commit()

    return {"status": "enabled", "message": "Gmail monitoring enabled"}


@properties_router.delete("/gmail/disable-monitoring")
async def disable_gmail_monitoring(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Disable Gmail inbox monitoring."""
    from app.db.models.credential import UserPreferences

    result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    prefs = result.scalar_one_or_none()
    if prefs:
        config = getattr(prefs, 'market_config', None) or {}
        config["gmail_monitoring_enabled"] = False
        prefs.market_config = config
        await db.commit()

    return {"status": "disabled", "message": "Gmail monitoring disabled"}


@properties_router.get("/gmail/monitoring-status")
async def get_monitoring_status(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get Gmail monitoring status."""
    from app.db.models.credential import UserPreferences

    result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    prefs = result.scalar_one_or_none()
    config = getattr(prefs, 'market_config', None) or {} if prefs else {}

    return {
        "enabled": config.get("gmail_monitoring_enabled", False),
    }


# ============ PIPELINE REPORT ENDPOINTS ============

@router.post("/reports/pipeline/generate")
async def generate_pipeline_report(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Generate a pipeline report."""
    from app.services.pipeline_report import generate_pipeline_report, render_report_html

    data = await generate_pipeline_report(current_user.id, db)
    html = render_report_html(data)

    return {
        "deals_by_stage": data.deals_by_stage,
        "stage_changes_this_week": data.stage_changes_this_week,
        "followups_due": data.followups_due,
        "new_properties_count": data.new_properties_count,
        "generated_at": data.generated_at.isoformat(),
        "html": html,
    }
