import asyncio
import json
import logging
import uuid
from typing import Any, Annotated

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, CurrentUser
from app.core.config import settings
from app.core.security import verify_token, decrypt_credential
from app.db.models.user import User
from app.db.models.chat import ChatSession, ChatMessage
from app.db.models.credential import SiteCredential, UserPreferences
from app.models.chat import (
    AgentType,
    Message,
    MessageRole,
    WorkflowStep,
    WorkflowStepStatus,
)
from app.services.chat_titles import backfill_session_title
from app.services.orchestrator import execute_tool
from app.services.analytics import get_analytics, MetricType, MetricEvent
from app.services.user_llm import resolve_user_llm, ResolvedLLM
from app.services.guardrails import (
    validate_message_size,
    rate_limiter,
    classify_message,
    check_subscription_limit,
    check_token_budget,
    record_token_usage,
    increment_session_usage,
)

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)

# Store active WebSocket connections
active_connections: dict[str, WebSocket] = {}


def _pre_orchestrator_guardrails(user_id: str, content: str) -> tuple[bool, str | None]:
    """Cheap, dependency-free pre-LLM guardrails shared by both chat WS endpoints.

    Runs (1) message-size validation and (2) the shared per-user sliding-window
    rate limit. Returns ``(ok, error_message)``; on ``ok=False`` the caller
    should send ``err`` as a system WS frame and skip the orchestrator (no
    session row, no tokens spent).

    Synchronous and side-effect-light on purpose so it can be unit-tested
    without a DB, LLM, or WebSocket. The BYOK-aware guards (topic classifier,
    subscription limit, token budget) stay inline in each endpoint because they
    carry per-call dependencies (``resolved_llm``, ``is_byok``). Using the
    module-level ``rate_limiter`` singleton here means both endpoints share one
    per-user quota: a user cannot bypass the session-scoped limit via ``/ws``.
    """
    ok, err = validate_message_size(content)
    if not ok:
        return False, err
    ok, err = rate_limiter.check(user_id)
    if not ok:
        return False, err
    return True, None


# Pydantic models for REST endpoints
from pydantic import BaseModel, field_serializer
from datetime import datetime, timezone


def _as_utc_iso(dt: datetime) -> str:
    """Serialize a DB datetime as tz-aware UTC ISO.

    chat_messages.created_at is a naive-UTC column; serializing it without
    an offset makes JS parse it as LOCAL time, skewing transcripts by hours
    next to the tz-aware live-WS timestamps. Stamp UTC explicitly on the
    way out.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class ChatSessionResponse(BaseModel):
    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    # Project link — lets the chat surface show an "In: {project}" pill vs the
    # "Free-form" pill and hide the promote affordances once a chat is attached.
    project_id: str | None = None
    project_name: str | None = None

    model_config = {"from_attributes": True}

    @field_serializer("created_at", "updated_at")
    def _ser_dt(self, dt: datetime) -> str:
        return _as_utc_iso(dt)


class PromoteSessionNewProject(BaseModel):
    """Inline project to create when promoting a chat with no existing target."""

    name: str
    property_address: str | None = None


class PromoteSessionRequest(BaseModel):
    """Attach a free-form chat to a project.

    Exactly one of ``project_id`` (existing project) or ``new_project``
    (create-and-attach) must be provided.
    """

    project_id: str | None = None
    new_project: PromoteSessionNewProject | None = None


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    agent_type: str | None
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at")
    def _ser_created(self, dt: datetime) -> str:
        return _as_utc_iso(dt)


@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_chat_sessions(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ChatSessionResponse]:
    """List all chat sessions for the current user."""
    result = await db.execute(
        select(ChatSession)
        .options(
            selectinload(ChatSession.messages),
            selectinload(ChatSession.project),
        )
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    sessions = result.scalars().all()

    backfilled = False
    for s in sessions:
        if backfill_session_title(s):
            backfilled = True
    if backfilled:
        await db.commit()

    return [
        ChatSessionResponse(
            id=s.id,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
            message_count=len(s.messages),
            project_id=s.project_id,
            project_name=s.project.name if s.project else None,
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def get_session_messages(
    session_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ChatMessageResponse]:
    """Get all messages for a chat session."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id, ChatMessage.visible == True)  # noqa: E712
        .order_by(ChatMessage.created_at)
    )
    messages = result.scalars().all()

    return [ChatMessageResponse.model_validate(m) for m in messages]


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChatSessionResponse:
    """Create a new chat session."""
    session = ChatSession(user_id=current_user.id, system_prompt_id="MASTER_DEFAULT")
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return ChatSessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=0,
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a chat session."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    await db.delete(session)
    await db.commit()


@router.post("/sessions/{session_id}/promote", response_model=ChatSessionResponse)
async def promote_chat_session(
    session_id: str,
    payload: PromoteSessionRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChatSessionResponse:
    """Attach a free-form chat to a project (existing or newly created).

    The chat's existing history is untouched — only *future* turns pick up
    the project context (see the WS handler's ``build_project_context`` call).
    """
    from app.db.models.project import Project

    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    # Resolve the target project: either an existing one owned by the user, or
    # a brand-new project created inline. Exactly one path must be provided.
    if payload.project_id and payload.new_project is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either project_id or new_project, not both",
        )
    if payload.new_project is not None:
        name = (payload.new_project.name or "").strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Project name is required",
            )
        project = Project(
            user_id=current_user.id,
            name=name,
            property_address=(payload.new_project.property_address or "").strip()
            or None,
            is_archived=False,
        )
        db.add(project)
        await db.flush()  # assign project.id before linking
    elif payload.project_id:
        proj_result = await db.execute(
            select(Project).where(
                Project.id == payload.project_id,
                Project.user_id == current_user.id,
            )
        )
        project = proj_result.scalar_one_or_none()
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either project_id or new_project",
        )

    session.project_id = project.id
    await db.commit()
    await db.refresh(session)

    return ChatSessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=len(session.messages),
        project_id=project.id,
        project_name=project.name,
    )


# Demo agent responses for simulation
DEMO_RESPONSES: dict[AgentType, dict[str, str]] = {
    AgentType.ORCHESTRATOR: {
        "greeting": "I'll help you analyze this property. Let me coordinate our specialized agents to gather the information you need.",
        "planning": "I've created a workflow to analyze this request. Our agents will now gather data from multiple sources.",
    },
    AgentType.DEMOGRAPHICS: {
        "working": "Accessing Census ACS data and analyzing trade area demographics...",
        "result": "Trade area analysis complete:\n- Population: 145,000 (5-mile radius)\n- Median HH Income: $78,500\n- Growth Rate: 2.3% YoY\n- Key Demographics: 35% families, 28% young professionals",
    },
    AgentType.TENANT_ROSTER: {
        "working": "Connecting to CoStar to retrieve current tenant roster...",
        "result": "Tenant roster retrieved:\n- 47 active tenants identified\n- Anchor tenants: Target, Best Buy, PetSmart\n- 12% vacancy rate (4 available spaces)\n- Mix: 40% retail, 35% dining, 25% services",
    },
    AgentType.FOOT_TRAFFIC: {
        "working": "Pulling foot traffic data from Placer.ai...",
        "result": "Foot traffic analysis:\n- Monthly visits: 285,000 avg\n- Peak days: Saturday, Sunday\n- Peak hours: 12-3 PM, 6-8 PM\n- YoY trend: +8% growth",
    },
    AgentType.VOID_ANALYSIS: {
        "working": "Running void analysis algorithm against market data...",
        "result": "Void analysis complete - Top opportunities:\n1. Fast Casual Dining (high demand, low supply)\n2. Fitness/Wellness (demographic match)\n3. Coffee/Cafe (foot traffic supports)\n4. Medical/Dental (underserved category)",
    },
    AgentType.NOTIFICATION: {
        "working": "Preparing client notification list...",
        "result": "Found 12 clients matching this opportunity:\n- 5 fast casual restaurant groups\n- 4 fitness franchise operators\n- 3 coffee shop chains\n\nReady to send notifications on your approval.",
    },
}


def get_workflow_for_task(task: str) -> list[WorkflowStep]:
    """Determine which agents to run based on the task."""
    steps: list[WorkflowStep] = []
    task_lower = task.lower()

    # Always start with orchestrator acknowledgment (handled separately)

    if any(word in task_lower for word in ["mall", "property", "analyze", "analysis"]):
        steps.append(
            WorkflowStep(
                id=str(uuid.uuid4()),
                agent_type=AgentType.DEMOGRAPHICS,
                description="Analyzing trade area demographics",
            )
        )
        steps.append(
            WorkflowStep(
                id=str(uuid.uuid4()),
                agent_type=AgentType.TENANT_ROSTER,
                description="Retrieving tenant roster",
            )
        )
        steps.append(
            WorkflowStep(
                id=str(uuid.uuid4()),
                agent_type=AgentType.FOOT_TRAFFIC,
                description="Analyzing foot traffic patterns",
            )
        )

    if any(word in task_lower for word in ["void", "opportunity", "gap", "missing"]):
        steps.append(
            WorkflowStep(
                id=str(uuid.uuid4()),
                agent_type=AgentType.VOID_ANALYSIS,
                description="Identifying tenant gaps",
            )
        )

    if any(word in task_lower for word in ["notify", "client", "email", "alert"]):
        steps.append(
            WorkflowStep(
                id=str(uuid.uuid4()),
                agent_type=AgentType.NOTIFICATION,
                description="Preparing client notifications",
            )
        )

    # Default workflow if nothing matched
    if not steps:
        steps.append(
            WorkflowStep(
                id=str(uuid.uuid4()),
                agent_type=AgentType.DEMOGRAPHICS,
                description="Gathering market data",
            )
        )

    return steps


async def send_ws_message(websocket: WebSocket, msg_type: str, data: Any) -> None:
    """Send a WebSocket message."""
    await websocket.send_json({"type": msg_type, "data": data})


async def simulate_agent_work(
    websocket: WebSocket,
    agent_type: AgentType,
    step_id: str,
) -> None:
    """Simulate an agent doing work and responding."""
    responses = DEMO_RESPONSES.get(agent_type, {})

    # Send "working" message
    working_msg = Message(
        role=MessageRole.AGENT,
        agent_type=agent_type,
        content=responses.get("working", "Processing..."),
        is_streaming=True,
    )
    await send_ws_message(websocket, "message", working_msg.model_dump(mode="json"))

    # Simulate work delay
    await asyncio.sleep(1.5)

    # Update workflow step to completed
    await send_ws_message(
        websocket,
        "workflow_update",
        {"step_id": step_id, "status": WorkflowStepStatus.COMPLETED.value},
    )

    # Send result message
    result_msg = Message(
        role=MessageRole.AGENT,
        agent_type=agent_type,
        content=responses.get("result", "Task completed."),
    )
    await send_ws_message(websocket, "message", result_msg.model_dump(mode="json"))


async def get_user_from_token(token: str, db: AsyncSession) -> User | None:
    """Validate token and return user."""
    from app.db.models.subscription import Subscription

    payload = verify_token(token)
    if payload is None or payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if user_id is None:
        return None

    result = await db.execute(
        select(User)
        .options(selectinload(User.subscription).selectinload(Subscription.plan))
        .where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def save_message_to_db(
    session_id: str,
    role: str,
    content: str,
    agent_type: str | None = None,
    visible: bool = True,
) -> None:
    """Save a message to the database using a new session."""
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        message = ChatMessage(
            session_id=session_id,
            role=role,
            agent_type=agent_type,
            content=content,
            visible=visible,
        )
        db.add(message)
        await db.commit()


async def load_session_history(session_id: str) -> list[dict[str, str]]:
    """Load existing messages for a session and format for Claude."""
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        # Only replay user-facing rows. Intermediate work product (raw tool
        # outputs persisted with visible=False by the legacy path) must not
        # re-enter the model's context on later turns — it bloats the prompt
        # and reinjects untrusted tool dumps as if they were assistant text.
        result = await db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.visible == True,  # noqa: E712
            )
            .order_by(ChatMessage.created_at)
        )
        messages = result.scalars().all()

        # Format for Claude conversation history
        history = []
        for msg in messages:
            if msg.role == "user":
                history.append({"role": "user", "content": msg.content})
            elif msg.role == "agent":
                # Agent messages are assistant responses for Claude
                history.append({"role": "assistant", "content": msg.content})

        return history


async def get_session_messages_for_frontend(session_id: str) -> list[dict]:
    """Load messages formatted for the frontend."""
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        messages = result.scalars().all()

        return [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "agent_type": msg.agent_type,
                "timestamp": _as_utc_iso(msg.created_at) if msg.created_at else None,
            }
            for msg in messages
        ]


async def get_user_siteusa_credential(user_id: str) -> SiteCredential | None:
    """Get the user's SitesUSA credential if available.

    Returns the credential regardless of verification status — the browser
    agents handle login / session management themselves.  Gating on
    ``is_verified`` previously hid the tools entirely from Claude whenever
    verification hadn't completed (CAPTCHA sites, first-time save, etc.).
    """
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        result = await db.execute(
            select(SiteCredential).where(
                SiteCredential.user_id == user_id,
                SiteCredential.site_name == "siteusa",
            )
        )
        credential = result.scalar_one_or_none()
        if credential:
            return credential
        return None


async def get_user_placer_credential(user_id: str) -> SiteCredential | None:
    """Get the user's Placer.ai credential if available.

    Returns the credential regardless of verification status — the browser
    agents handle login / session management themselves.
    """
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        result = await db.execute(
            select(SiteCredential).where(
                SiteCredential.user_id == user_id,
                SiteCredential.site_name == "placer",
            )
        )
        credential = result.scalar_one_or_none()
        if credential:
            return credential
        return None


async def get_user_costar_credential(user_id: str) -> SiteCredential | None:
    """Get the user's CoStar credential if available.

    Returns the credential regardless of verification status — the browser
    agents handle login / session management themselves.
    """
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        result = await db.execute(
            select(SiteCredential).where(
                SiteCredential.user_id == user_id,
                SiteCredential.site_name == "costar",
            )
        )
        credential = result.scalar_one_or_none()
        if credential:
            return credential
        return None


async def handle_tool_calls(
    websocket: WebSocket,
    tool_calls: list[dict],
    session_id: str | None,
    user_id: str,
    conversation_history: list[dict[str, str]],
    user_context: str | None,
    has_imported_data: dict[str, bool] | None = None,
    document_context: dict | None = None,
    project_context: dict | None = None,
    system_prompt_id: str | None = None,
    analysis_type: str | None = None,
    depth: int = 0,
    resolved_llm: ResolvedLLM | None = None,
    internal: bool = False,
) -> list[dict] | None:
    """
    Handle tool calls from Claude's native tool use.

    This function:
    1. Creates workflow UI for user feedback
    2. Executes each tool in parallel (when possible)
    3. Sends results back to Claude for synthesis
    4. Returns the final synthesized response

    ``internal=True`` runs the tools purely as internal work product for
    the specialist-routing path: the raw tool outputs are NOT emitted as
    ``message`` events and NOT persisted, and the competing orchestrator
    synthesis is skipped (the caller owns the single user-facing synthesis).
    In that mode the executed tool results are returned so the caller can
    fold them into its own synthesis input. The default (``internal=False``)
    is the legacy monolithic path, where this function's synthesis IS the
    user-facing answer.
    """
    from app.core.config import settings as _settings

    if depth >= _settings.guardrail_tool_recursion_max_depth:
        logger.warning("[handle_tools] recursion depth %d reached max, stopping", depth)
        summary_msg = Message(
            role=MessageRole.AGENT,
            agent_type=AgentType.ORCHESTRATOR,
            content="I've gathered the available data. Let me summarize what I found so far.",
        )
        await send_ws_message(websocket, "message", summary_msg.model_dump(mode="json"))
        return

    logger.debug("[handle_tools] tool_calls=%d depth=%d", len(tool_calls), depth)
    from app.services.orchestrator import get_orchestrator_response

    # Map tool names to AgentType for UI
    tool_to_agent_type = {
        "business_search": AgentType.TENANT_ROSTER,
        "demographics_analysis": AgentType.DEMOGRAPHICS,
        "tenant_roster": AgentType.TENANT_ROSTER,
        "void_analysis": AgentType.VOID_ANALYSIS,
        "traffic_counts": AgentType.FOOT_TRAFFIC,
        "foot_traffic": AgentType.FOOT_TRAFFIC,
        "document_search": AgentType.ANALYST,
    }

    tool_descriptions = {
        "business_search": "Searching nearby businesses",
        "demographics_analysis": "Analyzing trade area demographics",
        "tenant_roster": "Fetching tenant roster",
        "void_analysis": "Identifying tenant gaps & opportunities",
        "traffic_counts": "Looking up daily traffic counts",
        "foot_traffic": "Pulling foot-traffic metrics",
        "document_search": "Searching project documents",
    }

    # Create workflow steps for UI
    workflow: list[WorkflowStep] = []
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        workflow.append(
            WorkflowStep(
                id=tool_call["id"],
                agent_type=tool_to_agent_type.get(tool_name, AgentType.ORCHESTRATOR),
                description=tool_descriptions.get(tool_name, tool_name.replace("_", " ").title()),
            )
        )

    # Send workflow init to UI
    if workflow:
        await send_ws_message(
            websocket,
            "workflow_init",
            [step.model_dump(mode="json") for step in workflow],
        )
        await asyncio.sleep(0.2)

    # Mark all tools as running
    for step in workflow:
        await send_ws_message(
            websocket,
            "workflow_update",
            {"step_id": step.id, "status": WorkflowStepStatus.RUNNING.value},
        )

    # Only block tools for connectors explicitly disabled by the user.
    # Other statuses (needs_reauth, error, stale) should still attempt
    # execution — the browser agents handle login/session management
    # themselves and the health-probe status does not mean the credential
    # is unusable.
    _BLOCKED_STATUSES = {"disabled"}

    # Tool execution timeout (seconds)
    TOOL_TIMEOUT_SECONDS = 45

    # Tools whose primary geographic argument should fall back to the active
    # project's property address when the model didn't (or couldn't) supply
    # one. Maps tool_name -> the param key that holds the address/location.
    _LOCATION_PARAM_BY_TOOL = {
        "business_search": "location",
        "demographics_analysis": "address",
        "tenant_roster": "address",
        "void_analysis": "address",
        "traffic_counts": "address",
        "foot_traffic": "address",
    }

    def _is_unusable_location(value: object) -> bool:
        """True when a tool's location/address arg clearly can't be geocoded.

        Catches empty strings and the vague placeholder phrasings models fall
        back to when they read 'the location' or 'this property' out of the
        system prompt without a concrete address to paste in.
        """
        if not isinstance(value, str):
            return True
        stripped = value.strip().lower()
        if not stripped:
            return True
        _VAGUE = {
            "the location", "this location", "the property", "this property",
            "the address", "here", "unknown", "n/a", "na", "none",
        }
        return stripped in _VAGUE

    # Execute tools in parallel
    async def execute_single_tool(tool_call: dict) -> dict:
        tool_name = tool_call["name"]
        tool_input = tool_call["input"]
        tool_input_keys = list(tool_input.keys()) if isinstance(tool_input, dict) else []
        logger.debug("[handle_tools] execute tool=%s input_keys=%s", tool_name, tool_input_keys)

        # Fill the location/address arg from the project's property address
        # when the model omitted it or passed a vague placeholder. The address
        # lives in project_context as unstructured prose in the system prompt,
        # so without this fallback a weak extraction sends Google Places a
        # query with no geographic signal and we get global junk results.
        param_key = _LOCATION_PARAM_BY_TOOL.get(tool_name)
        if (
            param_key
            and isinstance(tool_input, dict)
            and project_context
            and isinstance(project_context.get("property"), dict)
        ):
            proj_addr = project_context["property"].get("address")
            if proj_addr and _is_unusable_location(tool_input.get(param_key)):
                logger.info(
                    "[handle_tools] enriching tool=%s %s from project address (was=%r)",
                    tool_name, param_key, tool_input.get(param_key),
                )
                tool_input = {**tool_input, param_key: proj_addr}

        try:
            result = await asyncio.wait_for(
                execute_tool(tool_name, tool_input, user_id, session_id=session_id),
                timeout=TOOL_TIMEOUT_SECONDS,
            )
            logger.debug("[handle_tools] tool=%s result_chars=%d", tool_name, len(result))
            return {
                "tool_call_id": tool_call["id"],
                "tool_name": tool_name,
                "result": result,
                "success": True,
            }
        except asyncio.TimeoutError:
            logger.warning("[handle_tools] tool=%s timed out after %ds", tool_name, TOOL_TIMEOUT_SECONDS)
            return {
                "tool_call_id": tool_call["id"],
                "tool_name": tool_name,
                "result": (
                    f"This is taking longer than expected. "
                    f"Try providing a more specific address with ZIP code for faster results."
                ),
                "success": False,
            }
        except Exception as e:
            logger.exception("[handle_tools] tool=%s failed", tool_name)
            return {
                "tool_call_id": tool_call["id"],
                "tool_name": tool_name,
                "result": f"Error executing {tool_name}: {str(e)}",
                "success": False,
            }

    # Run all tools in parallel
    logger.debug("[handle_tools] running tools=%d", len(tool_calls))
    tool_results = await asyncio.gather(*[execute_single_tool(tc) for tc in tool_calls])
    logger.debug("[handle_tools] completed tools=%d", len(tool_results))

    # Update workflow UI. Raw tool outputs are ALWAYS intermediate work
    # product — they are never a user-facing bubble, so they are emitted
    # hidden (and never persisted) regardless of which AgentType they map
    # to. Previously an unmapped tool defaulted to ORCHESTRATOR and leaked
    # its raw JSON into the transcript as a visible bubble.
    for result_dict in tool_results:
        tool_name = result_dict["tool_name"]
        result = result_dict["result"]
        tool_call_id = result_dict["tool_call_id"]

        # In internal (specialist-routing) mode tool execution stays fully
        # under the hood: no message frame, no DB row. The caller folds the
        # returned results into its own single synthesis.
        if not internal:
            agent_type = tool_to_agent_type.get(tool_name, AgentType.ORCHESTRATOR)
            tool_msg = Message(
                role=MessageRole.AGENT,
                agent_type=agent_type,
                content=result,
                visible=False,
            )
            await send_ws_message(
                websocket, "message", tool_msg.model_dump(mode="json")
            )
            if session_id:
                await save_message_to_db(
                    session_id, "agent", result, tool_name, visible=False
                )

        # Mark step as completed (the progress strip stays live in both modes)
        await send_ws_message(
            websocket,
            "workflow_update",
            {"step_id": tool_call_id, "status": WorkflowStepStatus.COMPLETED.value},
        )

    # Now send results back to Claude for synthesis. Detect gateway
    # "[TOOL_ERROR kind=…] user_message" sentinels (emitted by the
    # reliability envelope) and pass them as structured failures so
    # ``_build_orchestrator_request`` can frame them with [FAILED: kind]
    # for the synthesis prompt.
    pending_results: list[dict] = []
    for r in tool_results:
        result_text = r["result"]
        entry: dict = {"tool_name": r["tool_name"], "result": result_text}
        if isinstance(result_text, str) and result_text.startswith("[TOOL_ERROR"):
            try:
                head, msg = result_text.split("]", 1)
                kind = head.split("kind=", 1)[1].strip()
                entry["error_kind"] = kind
                entry["user_message"] = msg.strip()
            except Exception:
                entry["error_kind"] = "unknown"
                entry["user_message"] = result_text
        elif r.get("success") is False:
            entry["error_kind"] = "timeout_or_exception"
            entry["user_message"] = result_text
        pending_results.append(entry)

    # Internal mode: hand the raw results back to the caller instead of
    # running (and persisting) a competing orchestrator synthesis here. The
    # specialist-routing turn owns the single user-facing synthesis, so a
    # synthesis in this function would double-persist and leak a second
    # "orchestrator" bubble into the transcript.
    if internal:
        return pending_results

    try:
        synthesis_response = await _stream_orchestrator_to_ws(
            websocket,
            session_id=session_id or "",
            user_id=user_id or "",
            conversation_history=conversation_history,
            user_context=user_context,
            has_imported_data=has_imported_data,
            document_context=document_context,
            project_context=project_context,
            system_prompt_id=system_prompt_id,
            analysis_type=analysis_type,
            memory_context=None,
            resolved_llm=resolved_llm,
            pending_tool_results=pending_results,
        )

        # Record tokens from synthesis call (skipped if user is on BYOK)
        await record_token_usage(
            user_id,
            synthesis_response.get("input_tokens", 0),
            synthesis_response.get("output_tokens", 0),
            is_byok=bool(resolved_llm and resolved_llm.is_byok),
        )

        if synthesis_response.get("tool_calls"):
            await handle_tool_calls(
                websocket=websocket,
                tool_calls=synthesis_response["tool_calls"],
                session_id=session_id,
                user_id=user_id,
                conversation_history=conversation_history,
                user_context=user_context,
                has_imported_data=has_imported_data,
                document_context=document_context,
                project_context=project_context,
                system_prompt_id=system_prompt_id,
                analysis_type=analysis_type,
                depth=depth + 1,
                resolved_llm=resolved_llm,
            )
        elif synthesis_response["content"]:
            # Text already streamed via text_delta + message_end.
            if session_id:
                await save_message_to_db(
                    session_id, "agent", synthesis_response["content"], "orchestrator"
                )
            conversation_history.append(
                {"role": "assistant", "content": synthesis_response["content"]}
            )

    except Exception as e:
        # Log the full cause for debugging but only send the safe
        # normalized message to the client — raw provider exceptions
        # can contain request details or key material.
        cause = e.__cause__ if e.__cause__ else e
        logger.exception("[handle_tools] synthesis failed: %s (cause: %s)", e, cause)
        error_msg = Message(
            role=MessageRole.SYSTEM,
            content=f"Error synthesizing results: {str(e)}",
        )
        await send_ws_message(websocket, "message", error_msg.model_dump(mode="json"))


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(default=""),
) -> None:
    """WebSocket endpoint for real-time chat with Claude orchestrator."""
    from app.core.database import async_session_factory
    from app.services.orchestrator import get_orchestrator_response, generate_conversation_title
    from app.services.places import resolve_business_to_address, extract_business_query_from_message
    from app.api.preferences import build_personalized_context
    from app.services.memory_service import get_memory_service

    async with async_session_factory() as db:
        user = await get_user_from_token(token, db) if token else None

        if user is None:
            await websocket.close(code=4001, reason="Unauthorized")
            return

        # Check if this is a new session or existing one
        is_new_session = session_id == "new"
        actual_session_id: str | None = None
        user_id = user.id  # Store user_id for later session creation

        # Fetch user preferences for personalized AI context
        # IMPORTANT: Use conversation_scoped_context to prevent cross-chat leakage
        # This excludes location-specific data (markets) by default
        user_context: str | None = None
        result = await db.execute(
            select(UserPreferences).where(UserPreferences.user_id == user_id)
        )
        user_prefs = result.scalar_one_or_none()
        if user_prefs:
            # Use build_conversation_scoped_context instead of build_personalized_context
            # to prevent cross-chat city leakage
            from app.api.preferences import build_conversation_scoped_context
            user_context = build_conversation_scoped_context(user_prefs)

        # Fetch user memory context for personalization
        memory_context: str | None = None
        try:
            memory_svc = get_memory_service(db)
            memory_context = await memory_svc.get_context_block(user_id)
        except Exception as e:
            logger.warning("Failed to load memory context for user %s: %s", user_id, e)

        # Resolve user's LLM provider (BYOK or platform default based on tier)
        user_resolved_llm: ResolvedLLM | None = None
        try:
            user_resolved_llm = await resolve_user_llm(db, user_id, user.tier)
            logger.debug(
                "Resolved LLM for user %s: provider=%s model=%s byok=%s",
                user_id, user_resolved_llm.provider, user_resolved_llm.model, user_resolved_llm.is_byok,
            )
        except Exception as e:
            logger.warning("Failed to resolve user LLM for %s, using platform default: %s", user_id, e)

        if not is_new_session:
            # Validate existing session
            result = await db.execute(
                select(ChatSession).where(
                    ChatSession.id == session_id,
                    ChatSession.user_id == user.id,
                )
            )
            chat_session = result.scalar_one_or_none()
            if chat_session is None:
                await websocket.close(code=4004, reason="Session not found")
                return
            actual_session_id = chat_session.id
        # For new sessions, we'll create the session lazily when the first message is sent

    await websocket.accept()
    # Track connection with user-specific key to avoid conflicts for "new" sessions
    connection_key = f"{user_id}:{session_id}"
    active_connections[connection_key] = websocket
    logger.debug("WebSocket accepted session=%s", session_id)

    try:
        # Load existing conversation history for Claude (only for existing sessions)
        conversation_history: list[dict[str, str]] = []
        doc_context: dict | None = None
        proj_context: dict | None = None
        session_prompt_id: str | None = None
        session_analysis_type: str | None = None
        if actual_session_id:
            logger.debug("Loading history session=%s", actual_session_id)
            conversation_history = await load_session_history(actual_session_id)
            logger.debug("Loaded messages=%d", len(conversation_history))
            # Load document/project context and prompt info for analysis sessions
            async with async_session_factory() as db:
                result = await db.execute(
                    select(ChatSession).where(ChatSession.id == actual_session_id)
                )
                chat_sess = result.scalar_one_or_none()
                if chat_sess:
                    # Project context takes precedence over document context
                    if chat_sess.project_id:
                        from app.services.project_context import build_project_context
                        proj_context = await build_project_context(db, chat_sess.project_id)
                    elif chat_sess.document_context:
                        doc_context = chat_sess.document_context
                    session_prompt_id = chat_sess.system_prompt_id
                    session_analysis_type = chat_sess.analysis_type

        # Track the current address being analyzed
        current_address: str | None = None
        if doc_context:
            current_address = doc_context.get("property_address")
        # Track if this is the first message (for title generation)
        is_first_message = len(conversation_history) == 0
        # For new sessions, don't send session_info yet - wait until first message
        if actual_session_id:
            await websocket.send_json({
                "type": "session_info",
                "data": {"session_id": actual_session_id},
            })

            # Send existing chat history to frontend
            if conversation_history:
                existing_messages = await get_session_messages_for_frontend(actual_session_id)
                await websocket.send_json({
                    "type": "history",
                    "data": existing_messages,
                })

        session_usage_counted = False

        while True:
            data = await websocket.receive_text()
            try:
                message_data = json.loads(data)
            except json.JSONDecodeError:
                continue
            user_content = message_data.get("content", "")

            # --- Guardrail checks (pre-LLM) ---
            # 1-2. Message size + per-user rate limit (shared with /ws so a
            # user cannot bypass either endpoint's limit by switching endpoints).
            ok, err = _pre_orchestrator_guardrails(user_id, user_content)
            if not ok:
                await send_ws_message(websocket, "message", Message(role=MessageRole.SYSTEM, content=err).model_dump(mode="json"))
                continue

            # 3. Topic classifier — forward BYOK context so the ambiguous-tier Haiku
            # classifier call uses the user's key, not the platform's
            ok, err = await classify_message(user_content, resolved_llm=user_resolved_llm)
            if not ok:
                await send_ws_message(websocket, "message", Message(role=MessageRole.SYSTEM, content=err).model_dump(mode="json"))
                continue

            # 4. Subscription session limit
            ok, err = await check_subscription_limit(user_id)
            if not ok:
                await send_ws_message(websocket, "message", Message(role=MessageRole.SYSTEM, content=err).model_dump(mode="json"))
                continue

            # 5. Token budget — BYOK users bypass platform budget; their own provider meters usage
            ok, err = await check_token_budget(
                user_id,
                is_byok=bool(user_resolved_llm and user_resolved_llm.is_byok),
            )
            if not ok:
                await send_ws_message(websocket, "message", Message(role=MessageRole.SYSTEM, content=err).model_dump(mode="json"))
                continue

            # Echo user message back
            user_message = Message(
                role=MessageRole.USER,
                content=user_content,
            )
            await send_ws_message(
                websocket, "message", user_message.model_dump(mode="json")
            )

            # Create session lazily on first message (only for new sessions)
            if actual_session_id is None and is_new_session:
                # Get system_prompt_id from message payload (default to MASTER_DEFAULT)
                requested_prompt_id = message_data.get("system_prompt_id", "MASTER_DEFAULT")
                requested_project_id = message_data.get("project_id")

                async with async_session_factory() as db:
                    # Generate title from the first message
                    title = None
                    try:
                        title = await generate_conversation_title(user_content, resolved_llm=user_resolved_llm)
                    except Exception:
                        pass  # Title generation is non-critical

                    chat_session = ChatSession(
                        user_id=user_id,
                        title=title,
                        system_prompt_id=requested_prompt_id,
                        project_id=requested_project_id,
                    )
                    db.add(chat_session)
                    await db.commit()
                    await db.refresh(chat_session)
                    actual_session_id = chat_session.id
                    session_prompt_id = requested_prompt_id

                    # Load project context if session is in a project
                    if requested_project_id:
                        from app.services.project_context import build_project_context
                        proj_context = await build_project_context(db, requested_project_id)

                # Send session info to frontend now that session exists
                await websocket.send_json({
                    "type": "session_info",
                    "data": {"session_id": actual_session_id},
                })

                # Notify frontend of title update
                if title:
                    await websocket.send_json({
                        "type": "title_update",
                        "data": {"session_id": actual_session_id, "title": title},
                    })

                is_first_message = False

            # Save user message to database
            if actual_session_id:
                await save_message_to_db(actual_session_id, "user", user_content)

            # Add user message to conversation history
            conversation_history.append({"role": "user", "content": user_content})

            # Generate title from first message (for existing sessions that don't have a title yet)
            if is_first_message and actual_session_id:
                is_first_message = False
                try:
                    title = await generate_conversation_title(user_content, resolved_llm=user_resolved_llm)
                    # Update session title in database
                    async with async_session_factory() as db:
                        result = await db.execute(
                            select(ChatSession).where(ChatSession.id == actual_session_id)
                        )
                        session = result.scalar_one_or_none()
                        if session:
                            session.title = title
                            await db.commit()
                    # Notify frontend of title update
                    await websocket.send_json({
                        "type": "title_update",
                        "data": {"session_id": actual_session_id, "title": title},
                    })
                except Exception:
                    pass  # Title generation is non-critical

            # Extract address if mentioned (improved heuristic)
            content_lower = user_content.lower()
            address_keywords = ["mall", "center", "plaza", "shopping", "property", "leasing flyer"]
            street_keywords = ["st", "street", "ave", "avenue", "rd", "road", "blvd", "boulevard", "drive", "dr", "way", "lane", "ln", "pkwy", "parkway", "hwy", "highway"]

            if not current_address:
                # Check for property/location keywords
                if any(word in content_lower for word in address_keywords):
                    current_address = user_content
                # Check for street keywords (with or without numbers)
                elif any(word in content_lower for word in street_keywords):
                    current_address = user_content
                # Check if message contains digits (likely an address)
                elif any(char.isdigit() for char in user_content):
                    current_address = user_content
                else:
                    # Try to extract business name + location for resolution
                    business_query = extract_business_query_from_message(user_content)
                    if business_query:
                        logger.debug("Detected business query")
                        # Try to resolve to an address using Google Places
                        resolved = await resolve_business_to_address(business_query)
                        if resolved:
                            business_name, resolved_address = resolved
                            current_address = resolved_address
                            logger.debug("Resolved business query to address")

            # Phase 1: hardcoded — Phase 2 wires up real import detection
            has_imported_data = {"costar": False, "placer": False}

            # ----------------------------------------------------------
            # Specialist routing (Phase 3) vs monolithic orchestrator
            # ----------------------------------------------------------
            if settings.enable_specialist_routing:
                from app.services.orchestrator import (
                    plan_workflow,
                    call_specialist,
                    synthesize_specialist_outputs,
                )

                try:
                    # Step 1: Plan which specialists to call
                    planning_context = dict(proj_context) if proj_context else {}
                    if doc_context:
                        planning_context["document_context"] = doc_context
                    specialist_plan = await plan_workflow(
                        user_content,
                        context=planning_context or None,
                        resolved_llm=user_resolved_llm,
                    )
                    logger.info("[chat] specialist plan: %s", specialist_plan)

                    # Send workflow init to frontend
                    specialist_steps = [
                        WorkflowStep(
                            id=f"specialist-{name}",
                            agent_type=AgentType.ORCHESTRATOR,
                            description=f"{name.title()} analyzing...",
                        )
                        for name in specialist_plan
                    ]
                    if specialist_steps:
                        await send_ws_message(
                            websocket,
                            "workflow_init",
                            [step.model_dump(mode="json") for step in specialist_steps],
                        )

                    # Step 2: Call each specialist in sequence
                    specialist_outputs: list[dict] = []
                    total_input_tokens = 0
                    total_output_tokens = 0

                    for i, spec_name in enumerate(specialist_plan):
                        step_id = f"specialist-{spec_name}"
                        await send_ws_message(
                            websocket,
                            "workflow_update",
                            {"step_id": step_id, "status": WorkflowStepStatus.RUNNING.value},
                        )

                        # Build messages for this specialist: include prior specialist outputs
                        spec_messages = list(conversation_history)
                        for prev_output in specialist_outputs:
                            if prev_output.get("content"):
                                spec_messages.append({
                                    "role": "assistant",
                                    "content": f"[{prev_output['specialist'].title()} findings]:\n{prev_output['content']}",
                                })
                                spec_messages.append({
                                    "role": "user",
                                    "content": "Continue the analysis using the above findings.",
                                })

                        spec_result = await call_specialist(
                            name=spec_name,
                            messages=spec_messages,
                            context=proj_context,
                            resolved_llm=user_resolved_llm,
                            project_context=proj_context,
                            document_context=doc_context,
                        )
                        total_input_tokens += spec_result.get("input_tokens", 0)
                        total_output_tokens += spec_result.get("output_tokens", 0)

                        # Handle tool calls from this specialist
                        if spec_result.get("tool_calls"):
                            await handle_tool_calls(
                                websocket=websocket,
                                tool_calls=spec_result["tool_calls"],
                                session_id=actual_session_id,
                                user_id=user_id,
                                conversation_history=spec_messages,
                                user_context=user_context,
                                has_imported_data=has_imported_data,
                                document_context=doc_context,
                                project_context=proj_context,
                                system_prompt_id=session_prompt_id,
                                analysis_type=session_analysis_type,
                                resolved_llm=user_resolved_llm,
                            )

                        specialist_outputs.append(spec_result)

                        await send_ws_message(
                            websocket,
                            "workflow_update",
                            {"step_id": step_id, "status": WorkflowStepStatus.COMPLETED.value},
                        )

                    # Step 3: Synthesize
                    if len(specialist_outputs) > 1 or not specialist_outputs[0].get("content"):
                        synthesis = await synthesize_specialist_outputs(
                            user_message=user_content,
                            specialist_outputs=specialist_outputs,
                            conversation_history=conversation_history,
                            resolved_llm=user_resolved_llm,
                            project_context=proj_context,
                        )
                        total_input_tokens += synthesis.get("input_tokens", 0)
                        total_output_tokens += synthesis.get("output_tokens", 0)
                        final_content = synthesis["content"]
                    else:
                        # Single specialist — use its output directly
                        final_content = specialist_outputs[0].get("content", "")

                    await record_token_usage(
                        user_id,
                        total_input_tokens,
                        total_output_tokens,
                        is_byok=bool(user_resolved_llm and user_resolved_llm.is_byok),
                    )
                    if not session_usage_counted:
                        session_usage_counted = True
                        await increment_session_usage(user_id)

                    if final_content:
                        synth_msg = Message(
                            role=MessageRole.AGENT,
                            agent_type=AgentType.ORCHESTRATOR,
                            content=final_content,
                        )
                        await send_ws_message(websocket, "message", synth_msg.model_dump(mode="json"))
                        if actual_session_id:
                            await save_message_to_db(actual_session_id, "agent", final_content, "orchestrator")
                        conversation_history.append({"role": "assistant", "content": final_content})

                except Exception as e:
                    logger.exception("[chat] specialist routing failed: %s", e)
                    error_msg = Message(
                        role=MessageRole.SYSTEM,
                        content=f"I'm having trouble connecting to my AI backend. Error: {str(e)}",
                    )
                    await send_ws_message(websocket, "message", error_msg.model_dump(mode="json"))
                continue

            # ----------------------------------------------------------
            # Monolithic orchestrator path (default, feature flag off)
            # ----------------------------------------------------------

            # Get orchestrator response with native tool calling
            try:
                response = await get_orchestrator_response(
                    conversation_history,
                    user_context=user_context,
                    has_imported_data=has_imported_data,
                    document_context=doc_context,
                    project_context=proj_context,
                    system_prompt_id=session_prompt_id,
                    analysis_type=session_analysis_type,
                    memory_context=memory_context,
                    resolved_llm=user_resolved_llm,
                )
            except Exception as e:
                error_msg = Message(
                    role=MessageRole.SYSTEM,
                    content=f"I'm having trouble connecting to my AI backend. Error: {str(e)}",
                )
                await send_ws_message(websocket, "message", error_msg.model_dump(mode="json"))
                continue

            # --- Post-LLM: record tokens and session usage ---
            # Skip recording when BYOK is active — user's tokens are metered by their own provider.
            await record_token_usage(
                user_id,
                response.get("input_tokens", 0),
                response.get("output_tokens", 0),
                is_byok=bool(user_resolved_llm and user_resolved_llm.is_byok),
            )
            if not session_usage_counted:
                session_usage_counted = True
                await increment_session_usage(user_id)

            # Check if Claude wants to use tools
            tool_calls = response.get("tool_calls", [])
            logger.debug(
                "[chat] tool_calls=%d stop_reason=%s",
                len(tool_calls),
                response.get("stop_reason"),
            )

            if tool_calls:
                logger.debug("[chat] executing tool_calls=%d", len(tool_calls))
                # Claude is requesting to use tools - execute them
                await handle_tool_calls(
                    websocket=websocket,
                    tool_calls=tool_calls,
                    session_id=actual_session_id,
                    user_id=user_id,
                    conversation_history=conversation_history,
                    user_context=user_context,
                    has_imported_data=has_imported_data,
                    document_context=doc_context,
                    project_context=proj_context,
                    system_prompt_id=session_prompt_id,
                    analysis_type=session_analysis_type,
                    resolved_llm=user_resolved_llm,
                )
            else:
                # No tools requested - just send the response
                if response["content"]:
                    orchestrator_msg = Message(
                        role=MessageRole.AGENT,
                        agent_type=AgentType.ORCHESTRATOR,
                        content=response["content"],
                    )
                    await send_ws_message(
                        websocket, "message", orchestrator_msg.model_dump(mode="json")
                    )

                    # Save orchestrator response to database
                    if actual_session_id:
                        await save_message_to_db(
                            actual_session_id, "agent", response["content"], "orchestrator"
                        )

                    # Add assistant response to history
                    conversation_history.append({"role": "assistant", "content": response["content"]})

            # Legacy agent workflow path (browser-based agents removed in Phase 1)
            tools_to_run = response.get("tools_to_run", [])
            if tools_to_run and current_address and not tool_calls:
                legacy_msg = Message(
                    role=MessageRole.AGENT,
                    agent_type=AgentType.ORCHESTRATOR,
                    content="Browser-based agent execution has been removed. Use CSV/PDF imports instead.",
                )
                await send_ws_message(websocket, "message", legacy_msg.model_dump(mode="json"))
                if actual_session_id:
                    await save_message_to_db(actual_session_id, "agent", legacy_msg.content, "orchestrator")

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected session=%s", session_id)
    except Exception as e:
        logger.exception("WebSocket error session=%s", session_id)
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": f"Server error: {str(e)}"}
            })
        except Exception:
            pass  # Connection may already be closed
    finally:
        if connection_key in active_connections:
            del active_connections[connection_key]
        logger.debug("WebSocket cleanup session=%s", session_id)


async def _stream_orchestrator_to_ws(
    websocket: WebSocket,
    *,
    session_id: str,
    user_id: str,
    conversation_history: list[dict[str, str]],
    user_context: str | None,
    has_imported_data: dict[str, bool],
    document_context: dict | None,
    project_context: dict | None,
    system_prompt_id: str | None,
    analysis_type: str | None,
    memory_context: str | None,
    resolved_llm: ResolvedLLM | None,
    pending_tool_results: list[dict] | None = None,
) -> dict:
    """Stream an orchestrator turn to the WebSocket.

    Emits these WS events:
      - ``message_start`` {msg_id, role:"agent", agent_type:"orchestrator"}
      - ``text_delta`` {msg_id, delta}
      - ``tool_use_start`` {msg_id, tool_id, tool_name}
      - ``message_end`` {msg_id, content, stop_reason, tool_calls?}

    Returns a buffered-style ``{content, tool_calls, stop_reason,
    input_tokens, output_tokens}`` dict so the caller can keep its
    existing tool-call branching / DB save logic without forking.

    Falls back to the buffered ``get_orchestrator_response`` call on
    any provider error or when ``settings.streaming_enabled`` is False.
    """
    from app.services.orchestrator import (
        get_orchestrator_response,
        get_orchestrator_response_stream,
    )
    from app.llm.types import LLMStreamChunk

    if not bool(getattr(settings, "streaming_enabled", True)):
        return await get_orchestrator_response(
            conversation_history,
            pending_tool_results=pending_tool_results,
            user_context=user_context,
            has_imported_data=has_imported_data,
            document_context=document_context,
            project_context=project_context,
            system_prompt_id=system_prompt_id,
            analysis_type=analysis_type,
            memory_context=memory_context,
            resolved_llm=resolved_llm,
        )

    msg_id = uuid.uuid4().hex
    await send_ws_message(
        websocket,
        "message_start",
        {
            "msg_id": msg_id,
            "role": "agent",
            "agent_type": "orchestrator",
        },
    )

    text_buffer: list[str] = []
    tool_calls_out: list[dict] = []
    stop_reason: str | None = None
    input_tokens = 0
    output_tokens = 0

    try:
        async for chunk in get_orchestrator_response_stream(
            conversation_history,
            pending_tool_results=pending_tool_results,
            user_context=user_context,
            has_imported_data=has_imported_data,
            document_context=document_context,
            project_context=project_context,
            system_prompt_id=system_prompt_id,
            analysis_type=analysis_type,
            memory_context=memory_context,
            resolved_llm=resolved_llm,
        ):
            if chunk.kind == "text_delta":
                text_buffer.append(chunk.text)
                await send_ws_message(
                    websocket,
                    "text_delta",
                    {"msg_id": msg_id, "delta": chunk.text},
                )
            elif chunk.kind == "tool_use_start":
                await send_ws_message(
                    websocket,
                    "tool_use_start",
                    {
                        "msg_id": msg_id,
                        "tool_id": chunk.tool_id,
                        "tool_name": chunk.tool_name,
                    },
                )
            elif chunk.kind == "tool_use_end" and chunk.tool_call is not None:
                tool_calls_out.append(
                    {
                        "id": chunk.tool_call.id,
                        "name": chunk.tool_call.name,
                        "input": chunk.tool_call.input,
                    }
                )
            elif chunk.kind == "message_stop":
                stop_reason = chunk.stop_reason
                input_tokens = chunk.input_tokens
                output_tokens = chunk.output_tokens
    except Exception as e:
        logger.exception(
            "[chat-ws] streaming failed, falling back to buffered for session=%s",
            session_id,
        )
        # Close the streaming message cleanly so the frontend can drop
        # the in-flight bubble; then fall back to the buffered path so
        # the user still gets a reply.
        await send_ws_message(
            websocket,
            "message_end",
            {
                "msg_id": msg_id,
                "content": "".join(text_buffer),
                "stop_reason": "stream_error",
                "tool_calls": [],
                "error": str(e),
            },
        )
        return await get_orchestrator_response(
            conversation_history,
            pending_tool_results=pending_tool_results,
            user_context=user_context,
            has_imported_data=has_imported_data,
            document_context=document_context,
            project_context=project_context,
            system_prompt_id=system_prompt_id,
            analysis_type=analysis_type,
            memory_context=memory_context,
            resolved_llm=resolved_llm,
        )

    content = "".join(text_buffer)
    await send_ws_message(
        websocket,
        "message_end",
        {
            "msg_id": msg_id,
            "content": content,
            "stop_reason": stop_reason,
            "tool_calls": tool_calls_out,
        },
    )

    return {
        "content": content,
        "tool_calls": tool_calls_out,
        "stop_reason": stop_reason,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


# Map specialist names to the right ``AgentType`` so the UI badges them
# distinctly in chat bubbles and the workflow strip.
_SPECIALIST_TO_AGENT_TYPE: dict[str, AgentType] = {
    "scout": AgentType.SCOUT,
    "analyst": AgentType.ANALYST,
    "matchmaker": AgentType.MATCHMAKER,
    "outreach": AgentType.OUTREACH,
}

_SPECIALIST_DESCRIPTIONS: dict[str, str] = {
    "scout": "Scout is searching nearby businesses and demographics…",
    "analyst": "Analyst is reviewing the trade area for gaps…",
    "matchmaker": "Matchmaker is identifying candidate tenants…",
    "outreach": "Outreach is drafting candidate emails…",
}


async def _extract_and_notify_facts(
    websocket: WebSocket,
    *,
    user_id: str,
    session_id: str,
    user_message: str,
    assistant_response: str,
    resolved_llm: ResolvedLLM | None,
) -> None:
    """Run the fact extractor and notify the client of any new candidates.

    Best-effort: runs to completion in the background but any failure
    is swallowed so the chat surface stays clean. Awaited by a wrapping
    ``asyncio.create_task`` in the caller — never block the response.
    """
    from app.services.fact_extractor import extract_facts_from_turn

    if not assistant_response or not user_message:
        return
    try:
        persisted = await extract_facts_from_turn(
            user_id=user_id,
            user_message=user_message,
            assistant_response=assistant_response,
            session_id=session_id,
            resolved_llm=resolved_llm,
        )
    except Exception:
        logger.exception("[chat-ws] fact extraction failed")
        return
    if not persisted:
        return
    try:
        await send_ws_message(
            websocket,
            "fact_candidates",
            {
                "facts": [
                    {
                        "id": f.id,
                        "text": f.text,
                        "category": f.category,
                        "confidence": f.confidence,
                    }
                    for f in persisted
                ],
            },
        )
    except Exception:
        # Connection may have closed before we got back to it. The DB
        # rows are still there for the user to review later.
        logger.debug(
            "[chat-ws] could not push fact_candidates over closed WS"
        )


def _schedule_fact_extraction(
    websocket: WebSocket,
    *,
    user_id: str,
    session_id: str,
    user_message: str,
    assistant_response: str,
    resolved_llm: ResolvedLLM | None,
) -> None:
    """Fire-and-forget; surface candidate fact set via ``fact_candidates`` WS event."""
    if not assistant_response or not user_message:
        return
    asyncio.create_task(
        _extract_and_notify_facts(
            websocket,
            user_id=user_id,
            session_id=session_id,
            user_message=user_message,
            assistant_response=assistant_response,
            resolved_llm=resolved_llm,
        )
    )


async def _notify_tenant_candidates(
    websocket: WebSocket,
    *,
    session_id: str,
    sink: list[dict],
) -> None:
    """Surface void-analysis tenant suggestions via a ``tenant_candidates`` event.

    Drains the per-turn capture sink (populated by ``analyze_voids_for_property``
    when a void runs this turn) and pushes the deduped tenant list so the chat
    UI can offer "save these as Contacts". Best-effort: an empty sink or a closed
    socket is a silent no-op, and the sink is cleared either way so candidates
    never leak into the next turn.
    """
    from app.services.tenant_promotion import MAX_PROMOTABLE_TENANTS

    if not sink:
        return
    seen: set[str] = set()
    tenants: list[dict] = []
    for t in sink:
        name = str(t.get("name", "")).strip()
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        tenants.append(t)
    sink.clear()
    if not tenants:
        return
    try:
        await send_ws_message(
            websocket,
            "tenant_candidates",
            {
                "session_id": session_id,
                "tenants": tenants[:MAX_PROMOTABLE_TENANTS],
                "source_address": tenants[0].get("source_address"),
            },
        )
    except Exception:
        logger.debug("[chat-ws] could not push tenant_candidates over closed WS")


async def _stream_specialist_to_ws(
    websocket: WebSocket,
    *,
    name: str,
    session_id: str,
    user_id: str,
    conversation_history: list[dict[str, str]],
    project_context: dict | None,
    document_context: dict | None,
    resolved_llm: ResolvedLLM | None,
    stream_to_client: bool = True,
) -> dict:
    """Stream a single specialist turn to the WebSocket.

    Mirrors ``_stream_orchestrator_to_ws`` but uses ``call_specialist_stream``
    and tags every emitted event with the specialist's ``AgentType``.

    When ``stream_to_client`` is False, the specialist runs silently: no
    ``message_start`` / ``text_delta`` / ``message_end`` / ``tool_use_start``
    frames are emitted to the client (the progress strip's
    ``workflow_update`` events still surface activity). The full content +
    tool_calls are still buffered and returned so the synthesis pass can
    use them. This keeps the user-facing surface to a single
    "Space Goose Assistant" bubble per turn.

    Returns the buffered-style ``{specialist, content, tool_calls,
    stop_reason, input_tokens, output_tokens}`` dict the existing
    routing branch was already designed around.
    """
    from app.llm.types import LLMStreamChunk
    from app.services.orchestrator import (
        call_specialist,
        call_specialist_stream,
    )

    agent_type = _SPECIALIST_TO_AGENT_TYPE.get(name, AgentType.ORCHESTRATOR)

    if not bool(getattr(settings, "streaming_enabled", True)):
        return await call_specialist(
            name=name,
            messages=conversation_history,
            resolved_llm=resolved_llm,
            project_context=project_context,
            document_context=document_context,
        )

    msg_id = uuid.uuid4().hex
    if stream_to_client:
        await send_ws_message(
            websocket,
            "message_start",
            {"msg_id": msg_id, "role": "agent", "agent_type": agent_type.value},
        )

    text_buffer: list[str] = []
    tool_calls_out: list[dict] = []
    stop_reason: str | None = None
    input_tokens = 0
    output_tokens = 0

    try:
        async for chunk in call_specialist_stream(
            name=name,
            messages=conversation_history,
            resolved_llm=resolved_llm,
            project_context=project_context,
            document_context=document_context,
        ):
            if chunk.kind == "text_delta":
                text_buffer.append(chunk.text)
                if stream_to_client:
                    await send_ws_message(
                        websocket,
                        "text_delta",
                        {"msg_id": msg_id, "delta": chunk.text},
                    )
            elif chunk.kind == "tool_use_start":
                if stream_to_client:
                    await send_ws_message(
                        websocket,
                        "tool_use_start",
                        {
                            "msg_id": msg_id,
                            "tool_id": chunk.tool_id,
                            "tool_name": chunk.tool_name,
                        },
                    )
            elif chunk.kind == "tool_use_end" and chunk.tool_call is not None:
                tool_calls_out.append(
                    {
                        "id": chunk.tool_call.id,
                        "name": chunk.tool_call.name,
                        "input": chunk.tool_call.input,
                    }
                )
            elif chunk.kind == "message_stop":
                stop_reason = chunk.stop_reason
                input_tokens = chunk.input_tokens
                output_tokens = chunk.output_tokens
    except Exception as e:
        logger.exception(
            "[chat-ws] specialist=%s streaming failed for session=%s",
            name,
            session_id,
        )
        if stream_to_client:
            await send_ws_message(
                websocket,
                "message_end",
                {
                    "msg_id": msg_id,
                    "content": "".join(text_buffer),
                    "stop_reason": "stream_error",
                    "tool_calls": [],
                    "error": str(e),
                },
            )
        return await call_specialist(
            name=name,
            messages=conversation_history,
            resolved_llm=resolved_llm,
            project_context=project_context,
            document_context=document_context,
        )

    content = "".join(text_buffer)
    if stream_to_client:
        await send_ws_message(
            websocket,
            "message_end",
            {
                "msg_id": msg_id,
                "content": content,
                "stop_reason": stop_reason,
                "tool_calls": tool_calls_out,
                "agent_type": agent_type.value,
            },
        )

    return {
        "specialist": name,
        "content": content,
        "tool_calls": tool_calls_out,
        "stop_reason": stop_reason,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


async def _run_specialist_routing_turn(
    websocket: WebSocket,
    *,
    user_id: str,
    session_id: str,
    user_content: str,
    conversation_history: list[dict[str, str]],
    proj_context: dict | None,
    doc_context: dict | None,
    user_context: str | None,
    memory_context: str | None,
    has_imported_data: dict[str, bool],
    s_prompt_id: str | None,
    s_analysis_type: str | None,
    user_resolved_llm: ResolvedLLM | None,
) -> dict:
    """Drive the specialist routing branch end-to-end for one user turn.

    Extracted from the ``/ws`` loop so the orchestration can be unit-
    tested independently of FastAPI's WebSocket lifecycle. Side-effects:
        * Emits ``workflow_init`` / ``workflow_update`` per specialist
          (a subtle progress strip). Specialist content is NOT streamed
          to the client — only the final synthesized "Space Goose
          Assistant" bubble is user-facing.
        * Calls ``handle_tool_calls`` for any tool requests a specialist
          returns (tool execution stays internal).
        * Persists only the final synthesized orchestrator message to
          the transcript (per-specialist output is treated as
          intermediate work product).
        * Mutates ``conversation_history`` in place with the final
          assistant message (so the caller can keep using it).
        * Schedules best-effort fact extraction on the final content.
        * Records token usage with BYOK awareness.

    When the clarification gate trips (vague input), specialist routing
    is skipped entirely and a single orchestrator clarifying turn is
    streamed instead (no ``workflow_init``).

    Returns a summary dict::

        {
            "specialist_plan": [...],
            "specialist_outputs": [{"specialist": ..., "content": ...}, ...],
            "final_content": str,
            "input_tokens": int,
            "output_tokens": int,
            "synthesized": bool,
        }
    """
    from app.services.orchestrator import (
        message_has_concrete_target,
        needs_clarification,
        plan_workflow,
    )

    # ----------------------------------------------------------
    # Clarification gate: if the user's message is too vague to
    # delegate (e.g. a bare "Analyze property" with no address),
    # skip specialist routing and stream a single orchestrator
    # clarifying question so the user only ever sees one
    # "Space Goose Assistant" response with no progress strip.
    #
    # TTFT: the gate is a serial LLM round-trip in front of every
    # turn. When the message already names a concrete target (a
    # street address / ZIP) or arrives with attached document /
    # project context, it is self-evidently READY — skip the gate
    # call entirely so the common broker flow pays one small LLM
    # call (planning) instead of two before the progress strip
    # appears. Planning is NOT launched speculatively: on a vague
    # turn we must not pay for a plan we are about to discard.
    # ----------------------------------------------------------
    planning_context: dict = {}
    if proj_context:
        planning_context.update(proj_context)
    if doc_context:
        planning_context["document_context"] = doc_context

    obviously_ready = bool(
        doc_context
        or proj_context
        or message_has_concrete_target(user_content)
    )
    needs_clar = False
    if not obviously_ready:
        needs_clar = await needs_clarification(
            user_content,
            context=planning_context or None,
            resolved_llm=user_resolved_llm,
        )

    if needs_clar:
        logger.info("[chat-ws] clarification gate tripped for session=%s", session_id)
        clar_history = list(conversation_history)
        clar_history.append(
            {
                "role": "user",
                "content": (
                    user_content
                    + "\n\n(Note: the user's message lacks enough concrete "
                    "detail to begin specialist work. Ask ONE concise "
                    "clarifying question for what you need to proceed — "
                    "e.g. the property address or the specific deal "
                    "question. Do not call tools.)"
                ),
            }
        )
        clar_result = await _stream_orchestrator_to_ws(
            websocket,
            session_id=session_id,
            user_id=user_id,
            conversation_history=clar_history,
            user_context=user_context,
            has_imported_data=has_imported_data,
            document_context=doc_context,
            project_context=proj_context,
            system_prompt_id=s_prompt_id,
            analysis_type=s_analysis_type,
            memory_context=memory_context,
            resolved_llm=user_resolved_llm,
        )
        clar_content = clar_result.get("content", "")
        if clar_content:
            await save_message_to_db(
                session_id, "agent", clar_content, "orchestrator"
            )
            conversation_history.append(
                {"role": "assistant", "content": clar_content}
            )
            _schedule_fact_extraction(
                websocket,
                user_id=user_id,
                session_id=session_id,
                user_message=user_content,
                assistant_response=clar_content,
                resolved_llm=user_resolved_llm,
            )
        await record_token_usage(
            user_id,
            clar_result.get("input_tokens", 0),
            clar_result.get("output_tokens", 0),
            is_byok=bool(user_resolved_llm and user_resolved_llm.is_byok),
        )
        return {
            "specialist_plan": [],
            "specialist_outputs": [],
            "final_content": clar_content,
            "input_tokens": clar_result.get("input_tokens", 0),
            "output_tokens": clar_result.get("output_tokens", 0),
            "synthesized": False,
        }

    # ----------------------------------------------------------
    # Specialist routing: plan, run each specialist silently
    # (no user-facing bubble), then always synthesize a single
    # "Space Goose Assistant" response.
    # ----------------------------------------------------------
    specialist_plan = await plan_workflow(
        user_content,
        context=planning_context or None,
        resolved_llm=user_resolved_llm,
    )
    logger.info("[chat-ws] specialist plan: %s", specialist_plan)

    workflow_steps_payload = [
        {
            "id": f"specialist-{spec_name}",
            "agent_type": _SPECIALIST_TO_AGENT_TYPE.get(
                spec_name, AgentType.ORCHESTRATOR
            ).value,
            "status": "pending",
            "description": _SPECIALIST_DESCRIPTIONS.get(
                spec_name, f"{spec_name.title()} working…"
            ),
        }
        for spec_name in specialist_plan
    ]
    if workflow_steps_payload:
        await send_ws_message(websocket, "workflow_init", workflow_steps_payload)

    spec_outputs: list[dict] = []
    spec_total_in = 0
    spec_total_out = 0
    for spec_name in specialist_plan:
        step_id = f"specialist-{spec_name}"
        await send_ws_message(
            websocket,
            "workflow_update",
            {
                "step_id": step_id,
                "status": "running",
                "agent_type": _SPECIALIST_TO_AGENT_TYPE.get(
                    spec_name, AgentType.ORCHESTRATOR
                ).value,
            },
        )

        spec_messages = list(conversation_history)
        for prev in spec_outputs:
            if prev.get("content"):
                spec_messages.append(
                    {
                        "role": "assistant",
                        "content": f"[{prev['specialist'].title()} findings]:\n{prev['content']}",
                    }
                )
                spec_messages.append(
                    {
                        "role": "user",
                        "content": "Continue the analysis using the above findings.",
                    }
                )

        spec_result = await _stream_specialist_to_ws(
            websocket,
            name=spec_name,
            session_id=session_id,
            user_id=user_id,
            conversation_history=spec_messages,
            project_context=proj_context,
            document_context=doc_context,
            resolved_llm=user_resolved_llm,
            stream_to_client=False,
        )
        spec_total_in += spec_result.get("input_tokens", 0)
        spec_total_out += spec_result.get("output_tokens", 0)

        if spec_result.get("tool_calls"):
            tool_results = await handle_tool_calls(
                websocket=websocket,
                tool_calls=spec_result["tool_calls"],
                session_id=session_id,
                user_id=user_id,
                conversation_history=spec_messages,
                user_context=user_context,
                has_imported_data=has_imported_data,
                document_context=doc_context,
                project_context=proj_context,
                system_prompt_id=s_prompt_id,
                analysis_type=s_analysis_type,
                resolved_llm=user_resolved_llm,
                internal=True,
            )
            # Fold the raw tool outputs into this specialist's findings so the
            # single downstream synthesis (and any later specialist in the
            # plan) can see the data. In internal mode handle_tool_calls does
            # not synthesize or persist — it only returns the executed results.
            if isinstance(tool_results, list) and tool_results:
                tool_block = "\n\n".join(
                    f"### {r.get('tool_name', 'tool')}\n{r.get('result', '')}"
                    for r in tool_results
                )
                merged = (spec_result.get("content") or "").rstrip()
                spec_result["content"] = (
                    f"{merged}\n\n{tool_block}" if merged else tool_block
                )

        spec_outputs.append(spec_result)
        await send_ws_message(
            websocket,
            "workflow_update",
            {"step_id": step_id, "status": "completed"},
        )

    synthesized = False
    final_content = ""
    if spec_outputs:
        synthesized = True
        synthesis_input = "\n\n---\n\n".join(
            f"### {o['specialist'].title()} findings\n{o['content']}"
            for o in spec_outputs
            if o.get("content")
        )
        synth_history = list(conversation_history)
        if synthesis_input:
            synth_history.append(
                {
                    "role": "user",
                    "content": (
                        "Synthesize the specialist findings into a "
                        "single concise answer for the user:\n\n"
                        + synthesis_input
                    ),
                }
            )
        synth = await _stream_orchestrator_to_ws(
            websocket,
            session_id=session_id,
            user_id=user_id,
            conversation_history=synth_history,
            user_context=user_context,
            has_imported_data=has_imported_data,
            document_context=doc_context,
            project_context=proj_context,
            system_prompt_id=s_prompt_id,
            analysis_type=s_analysis_type,
            memory_context=memory_context,
            resolved_llm=user_resolved_llm,
        )
        final_content = synth.get("content", "")
        spec_total_in += synth.get("input_tokens", 0)
        spec_total_out += synth.get("output_tokens", 0)
        if final_content:
            await save_message_to_db(
                session_id, "agent", final_content, "orchestrator"
            )
            conversation_history.append(
                {"role": "assistant", "content": final_content}
            )
            _schedule_fact_extraction(
                websocket,
                user_id=user_id,
                session_id=session_id,
                user_message=user_content,
                assistant_response=final_content,
                resolved_llm=user_resolved_llm,
            )
    else:
        # Empty plan: nothing to synthesize. Tokens already zero.
        synthesized = False
        final_content = ""

    await record_token_usage(
        user_id,
        spec_total_in,
        spec_total_out,
        is_byok=bool(user_resolved_llm and user_resolved_llm.is_byok),
    )

    return {
        "specialist_plan": specialist_plan,
        "specialist_outputs": spec_outputs,
        "final_content": final_content,
        "input_tokens": spec_total_in,
        "output_tokens": spec_total_out,
        "synthesized": synthesized,
    }


@router.websocket("/ws")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    token: str = Query(default=""),
) -> None:
    """
    Simplified WebSocket endpoint for ChatGPT-style interaction.

    Key differences from /ws/{session_id}:
    - Single connection per user (not per session)
    - Session ID passed in message payload
    - History loaded via REST API, not WebSocket
    - Session created lazily on first message
    """
    from app.core.database import async_session_factory
    from app.services.orchestrator import get_orchestrator_response, generate_conversation_title
    from app.services.places import resolve_business_to_address, extract_business_query_from_message
    from app.api.preferences import build_personalized_context
    from app.services.memory_service import get_memory_service

    # Authenticate user
    async with async_session_factory() as db:
        user = await get_user_from_token(token, db) if token else None
        if user is None:
            await websocket.close(code=4001, reason="Unauthorized")
            return

        user_id = user.id

        # Fetch user preferences
        # IMPORTANT: Use conversation_scoped_context to prevent cross-chat leakage
        user_context: str | None = None
        result = await db.execute(
            select(UserPreferences).where(UserPreferences.user_id == user_id)
        )
        user_prefs = result.scalar_one_or_none()
        if user_prefs:
            from app.api.preferences import build_conversation_scoped_context
            user_context = build_conversation_scoped_context(user_prefs)

        # Fetch user memory context for personalization
        memory_context: str | None = None
        try:
            memory_svc = get_memory_service(db)
            memory_context = await memory_svc.get_context_block(user_id)
        except Exception as e:
            logger.warning("Failed to load memory context for user %s: %s", user_id, e)

        # Resolve user's LLM provider (BYOK or platform default based on tier)
        user_resolved_llm: ResolvedLLM | None = None
        try:
            user_resolved_llm = await resolve_user_llm(db, user_id, user.tier)
        except Exception as e:
            logger.warning("Failed to resolve user LLM for %s: %s", user_id, e)

    await websocket.accept()
    connection_key = f"chat:{user_id}"
    active_connections[connection_key] = websocket
    logger.debug("Chat WebSocket connected")

    # Track conversation state per session
    conversation_histories: dict[str, list[dict[str, str]]] = {}
    current_addresses: dict[str, str] = {}
    document_contexts: dict[str, dict | None] = {}
    project_contexts: dict[str, dict | None] = {}
    session_prompt_ids: dict[str, str | None] = {}
    session_analysis_types: dict[str, str | None] = {}
    # Reference to the in-flight orchestrator task, if any, so a
    # client-side ``cancel`` event can interrupt streaming cleanly.
    in_flight_task: asyncio.Task | None = None

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message_data = json.loads(data)
            except json.JSONDecodeError:
                continue

            # Allow the client to interrupt an in-flight turn. We treat
            # the cancel as best-effort: cancelling mid-stream raises
            # ``asyncio.CancelledError`` inside ``_stream_orchestrator_to_ws``
            # which then bubbles back to this loop, where the
            # ``finally`` block ensures the connection stays healthy.
            if message_data.get("type") == "cancel":
                if in_flight_task and not in_flight_task.done():
                    in_flight_task.cancel()
                    logger.info("[chat-ws] client cancelled in-flight turn")
                continue

            session_id = message_data.get("session_id")
            user_content = message_data.get("content", "")

            if not user_content.strip():
                continue

            # --- Guardrail checks (pre-LLM) ---
            # Size + per-user rate limit, shared with /ws/{session_id} via the
            # module-level singleton so a user cannot bypass the session-scoped
            # limit by using /ws. On reject, surface a system message and skip
            # the orchestrator (no session row created, no tokens spent).
            ok, err = _pre_orchestrator_guardrails(user_id, user_content)
            if not ok:
                await send_ws_message(websocket, "message", Message(role=MessageRole.SYSTEM, content=err).model_dump(mode="json"))
                continue

            # Create new session if needed
            if not session_id:
                # Get system_prompt_id from message payload (default to MASTER_DEFAULT)
                requested_prompt_id = message_data.get("system_prompt_id", "MASTER_DEFAULT")
                requested_project_id = message_data.get("project_id")

                async with async_session_factory() as db:
                    # Generate title from first message
                    title = None
                    try:
                        title = await generate_conversation_title(user_content, resolved_llm=user_resolved_llm)
                    except Exception:
                        pass

                    chat_session = ChatSession(
                        user_id=user_id,
                        title=title,
                        system_prompt_id=requested_prompt_id,
                        project_id=requested_project_id,
                    )
                    db.add(chat_session)
                    await db.commit()
                    await db.refresh(chat_session)
                    session_id = chat_session.id

                # Notify client of new session
                await websocket.send_json({
                    "type": "session_created",
                    "data": {"session_id": session_id, "title": title},
                })

                # Initialize conversation history for new session
                conversation_histories[session_id] = []
                document_contexts[session_id] = None
                project_contexts[session_id] = None
                session_prompt_ids[session_id] = requested_prompt_id
                session_analysis_types[session_id] = None

                if requested_project_id:
                    from app.services.project_context import build_project_context
                    async with async_session_factory() as db:
                        project_contexts[session_id] = await build_project_context(
                            db, requested_project_id
                        )

            # Load conversation history and document context if not cached
            if session_id not in conversation_histories:
                conversation_histories[session_id] = await load_session_history(session_id)
                # Load document/project context and prompt info for analysis sessions
                async with async_session_factory() as db:
                    result = await db.execute(
                        select(ChatSession).where(ChatSession.id == session_id)
                    )
                    chat_sess = result.scalar_one_or_none()
                    if chat_sess:
                        session_prompt_ids[session_id] = chat_sess.system_prompt_id
                        session_analysis_types[session_id] = chat_sess.analysis_type
                        if chat_sess.project_id:
                            from app.services.project_context import build_project_context
                            project_contexts[session_id] = await build_project_context(
                                db, chat_sess.project_id
                            )
                            document_contexts[session_id] = None
                        elif chat_sess.document_context:
                            document_contexts[session_id] = chat_sess.document_context
                            project_contexts[session_id] = None
                            # Pre-set address from document context
                            addr = chat_sess.document_context.get("property_address")
                            if addr:
                                current_addresses[session_id] = addr
                        else:
                            document_contexts[session_id] = None
                            project_contexts[session_id] = None
                    else:
                        document_contexts[session_id] = None
                        project_contexts[session_id] = None
                        session_prompt_ids[session_id] = None
                        session_analysis_types[session_id] = None

            conversation_history = conversation_histories[session_id]
            current_address = current_addresses.get(session_id)
            doc_context = document_contexts.get(session_id)
            proj_context = project_contexts.get(session_id)
            s_prompt_id = session_prompt_ids.get(session_id)
            s_analysis_type = session_analysis_types.get(session_id)

            # Echo user message
            user_message = Message(
                role=MessageRole.USER,
                content=user_content,
            )
            await send_ws_message(websocket, "message", user_message.model_dump(mode="json"))

            # Save user message
            await save_message_to_db(session_id, "user", user_content)
            conversation_history.append({"role": "user", "content": user_content})

            # Start capturing any tenant suggestions a void analysis produces
            # this turn so we can offer "save as Contacts" once it completes.
            from app.services.tenant_promotion import begin_tenant_capture

            tenant_sink = begin_tenant_capture()

            # Extract address if mentioned
            content_lower = user_content.lower()
            address_keywords = ["mall", "center", "plaza", "shopping", "property", "leasing flyer"]
            street_keywords = ["st", "street", "ave", "avenue", "rd", "road", "blvd", "boulevard", "drive", "dr", "way", "lane", "ln", "pkwy", "parkway", "hwy", "highway"]

            if not current_address:
                if any(word in content_lower for word in address_keywords):
                    current_address = user_content
                elif any(word in content_lower for word in street_keywords):
                    current_address = user_content
                elif any(char.isdigit() for char in user_content):
                    current_address = user_content
                else:
                    business_query = extract_business_query_from_message(user_content)
                    if business_query:
                        resolved = await resolve_business_to_address(business_query)
                        if resolved:
                            _, resolved_address = resolved
                            current_address = resolved_address

                if current_address:
                    current_addresses[session_id] = current_address

            # Phase 1: hardcoded — Phase 2 wires up real import detection
            has_imported_data = {"costar": False, "placer": False}

            # ----------------------------------------------------------------
            # Specialist routing branch. When enabled, we ask plan_workflow
            # for a list of specialists, stream each in turn (own bubble +
            # agent badge), then either use the last specialist's content
            # directly (single-specialist plan) or run a final streaming
            # synthesis. Falls back to the monolithic orchestrator path on
            # any failure so a routing bug never blocks chat.
            # ----------------------------------------------------------------
            if settings.enable_specialist_routing:
                try:
                    await _run_specialist_routing_turn(
                        websocket,
                        user_id=user_id,
                        session_id=session_id,
                        user_content=user_content,
                        conversation_history=conversation_history,
                        proj_context=proj_context,
                        doc_context=doc_context,
                        user_context=user_context,
                        memory_context=memory_context,
                        has_imported_data=has_imported_data,
                        s_prompt_id=s_prompt_id,
                        s_analysis_type=s_analysis_type,
                        user_resolved_llm=user_resolved_llm,
                    )
                    await _notify_tenant_candidates(
                        websocket, session_id=session_id, sink=tenant_sink
                    )
                    continue
                except Exception as e:
                    logger.exception(
                        "[chat-ws] specialist routing failed, falling back: %s", e
                    )
                    # fall through to the monolithic orchestrator path

            # Get orchestrator response — streams when settings.streaming_enabled,
            # otherwise falls back to the buffered call internally. Wrapped in
            # a task so a ``cancel`` event from the client can interrupt it.
            in_flight_task = asyncio.create_task(
                _stream_orchestrator_to_ws(
                    websocket,
                    session_id=session_id,
                    user_id=user_id,
                    conversation_history=conversation_history,
                    user_context=user_context,
                    has_imported_data=has_imported_data,
                    document_context=doc_context,
                    project_context=proj_context,
                    system_prompt_id=s_prompt_id,
                    analysis_type=s_analysis_type,
                    memory_context=memory_context,
                    resolved_llm=user_resolved_llm,
                )
            )
            try:
                response = await in_flight_task
            except asyncio.CancelledError:
                logger.info("[chat-ws] in-flight orchestrator cancelled")
                setIsProcessing_payload = {
                    "type": "message_end",
                    "data": {
                        "msg_id": "cancelled",
                        "content": "",
                        "stop_reason": "cancelled",
                        "tool_calls": [],
                    },
                }
                try:
                    await websocket.send_json(setIsProcessing_payload)
                except Exception:
                    pass
                in_flight_task = None
                continue
            except Exception as e:
                in_flight_task = None
                error_msg = Message(
                    role=MessageRole.SYSTEM,
                    content=f"I'm having trouble connecting to my AI backend. Error: {str(e)}",
                )
                await send_ws_message(websocket, "message", error_msg.model_dump(mode="json"))
                continue
            in_flight_task = None

            tool_calls = response.get("tool_calls", [])
            logger.debug(
                "[chat-ws] tool_calls=%d text_chars=%d",
                len(tool_calls),
                len(response.get("content", "")),
            )

            if tool_calls:
                logger.debug("[chat-ws] executing tool_calls=%d", len(tool_calls))
                await handle_tool_calls(
                    websocket=websocket,
                    tool_calls=tool_calls,
                    session_id=session_id,
                    user_id=user_id,
                    conversation_history=conversation_history,
                    user_context=user_context,
                    has_imported_data=has_imported_data,
                    document_context=doc_context,
                    project_context=proj_context,
                    system_prompt_id=s_prompt_id,
                    analysis_type=s_analysis_type,
                    resolved_llm=user_resolved_llm,
                )
            elif response["content"]:
                # The text was already streamed via text_delta + message_end.
                # We still need to persist the final transcript and append
                # to the in-memory conversation history.
                await save_message_to_db(
                    session_id, "agent", response["content"], "orchestrator"
                )
                conversation_history.append(
                    {"role": "assistant", "content": response["content"]}
                )
                _schedule_fact_extraction(
                    websocket,
                    user_id=user_id,
                    session_id=session_id,
                    user_message=user_content,
                    assistant_response=response["content"],
                    resolved_llm=user_resolved_llm,
                )

            # A void analysis may have run via a tool this turn; surface any
            # promotable tenants so the UI can offer "save as Contacts".
            await _notify_tenant_candidates(
                websocket, session_id=session_id, sink=tenant_sink
            )

            # Legacy agent workflow path (browser-based agents removed in Phase 1)
            tools_to_run = response.get("tools_to_run", [])
            if tools_to_run and current_address and not tool_calls:
                legacy_msg = Message(
                    role=MessageRole.AGENT,
                    agent_type=AgentType.ORCHESTRATOR,
                    content="Browser-based agent execution has been removed. Use CSV/PDF imports instead.",
                )
                await send_ws_message(websocket, "message", legacy_msg.model_dump(mode="json"))
                await save_message_to_db(session_id, "agent", legacy_msg.content, "orchestrator")

    except WebSocketDisconnect:
        logger.info("Chat WebSocket disconnected")
    except Exception as e:
        logger.exception("Chat WebSocket error")
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": f"Server error: {str(e)}"}
            })
        except Exception:
            pass
    finally:
        if connection_key in active_connections:
            del active_connections[connection_key]
        logger.debug("Chat WebSocket cleanup")


# run_agent_workflow removed in Phase 1 rearchitecture -- browser-based agents deleted
