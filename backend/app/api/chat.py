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


# Pydantic models for REST endpoints
from pydantic import BaseModel
from datetime import datetime


class ChatSessionResponse(BaseModel):
    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    agent_type: str | None
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_chat_sessions(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ChatSessionResponse]:
    """List all chat sessions for the current user."""
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
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
    payload = verify_token(token)
    if payload is None or payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if user_id is None:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
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
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
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
                "timestamp": msg.created_at.isoformat() if msg.created_at else None,
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
) -> None:
    """
    Handle tool calls from Claude's native tool use.

    This function:
    1. Creates workflow UI for user feedback
    2. Executes each tool in parallel (when possible)
    3. Sends results back to Claude for synthesis
    4. Returns the final synthesized response
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
    }

    tool_descriptions = {
        "business_search": "Searching nearby businesses",
        "demographics_analysis": "Analyzing trade area demographics",
        "tenant_roster": "Fetching tenant roster",
        "void_analysis": "Identifying tenant gaps & opportunities",
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

    # Execute tools in parallel
    async def execute_single_tool(tool_call: dict) -> dict:
        tool_name = tool_call["name"]
        tool_input = tool_call["input"]
        tool_input_keys = list(tool_input.keys()) if isinstance(tool_input, dict) else []
        logger.debug("[handle_tools] execute tool=%s input_keys=%s", tool_name, tool_input_keys)

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

    # Send results for each tool and update workflow UI
    for result_dict in tool_results:
        tool_name = result_dict["tool_name"]
        result = result_dict["result"]
        tool_call_id = result_dict["tool_call_id"]

        # Send tool result as a message (hidden from UI — orchestrator will summarize)
        agent_type = tool_to_agent_type.get(tool_name, AgentType.ORCHESTRATOR)
        is_intermediate = agent_type != AgentType.ORCHESTRATOR
        tool_msg = Message(
            role=MessageRole.AGENT,
            agent_type=agent_type,
            content=result,
            visible=not is_intermediate,
        )
        await send_ws_message(websocket, "message", tool_msg.model_dump(mode="json"))

        # Save to database
        if session_id:
            await save_message_to_db(session_id, "agent", result, tool_name, visible=not is_intermediate)

        # Mark step as completed
        await send_ws_message(
            websocket,
            "workflow_update",
            {"step_id": tool_call_id, "status": WorkflowStepStatus.COMPLETED.value},
        )

    # Now send results back to Claude for synthesis
    pending_results = [
        {"tool_name": r["tool_name"], "result": r["result"]}
        for r in tool_results
    ]

    try:
        synthesis_response = await get_orchestrator_response(
            conversation_history,
            pending_tool_results=pending_results,
            user_context=user_context,
            has_imported_data=has_imported_data,
            document_context=document_context,
            project_context=project_context,
            system_prompt_id=system_prompt_id,
            analysis_type=analysis_type,
            resolved_llm=resolved_llm,
        )

        # Record tokens from synthesis call (skipped if user is on BYOK)
        await record_token_usage(
            user_id,
            synthesis_response.get("input_tokens", 0),
            synthesis_response.get("output_tokens", 0),
            is_byok=bool(resolved_llm and resolved_llm.is_byok),
        )

        # Check if Claude wants to use more tools (rare, but possible)
        if synthesis_response.get("tool_calls"):
            # Recursive call for additional tools (depth-capped)
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
            # Send synthesized response
            synthesis_msg = Message(
                role=MessageRole.AGENT,
                agent_type=AgentType.ORCHESTRATOR,
                content=synthesis_response["content"],
            )
            await send_ws_message(websocket, "message", synthesis_msg.model_dump(mode="json"))

            if session_id:
                await save_message_to_db(session_id, "agent", synthesis_response["content"], "orchestrator")

            conversation_history.append({"role": "assistant", "content": synthesis_response["content"]})

    except Exception as e:
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
            # 1. Message size
            ok, err = validate_message_size(user_content)
            if not ok:
                await send_ws_message(websocket, "message", Message(role=MessageRole.SYSTEM, content=err).model_dump(mode="json"))
                continue

            # 2. Rate limit
            ok, err = rate_limiter.check(user_id)
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

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message_data = json.loads(data)
            except json.JSONDecodeError:
                continue

            session_id = message_data.get("session_id")
            user_content = message_data.get("content", "")

            if not user_content.strip():
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

            # Get orchestrator response (with document context and prompt ID for analysis sessions)
            try:
                response = await get_orchestrator_response(
                    conversation_history,
                    user_context=user_context,
                    has_imported_data=has_imported_data,
                    document_context=doc_context,
                    project_context=proj_context,
                    system_prompt_id=s_prompt_id,
                    analysis_type=s_analysis_type,
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

            # Check if Claude wants to use tools (native tool calling)
            tool_calls = response.get("tool_calls", [])
            logger.debug(
                "[chat-ws] tool_calls=%d text_chars=%d",
                len(tool_calls),
                len(response.get("content", "")),
            )

            if tool_calls:
                logger.debug("[chat-ws] executing tool_calls=%d", len(tool_calls))
                # Claude is requesting to use tools - execute them
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
                # No tools requested - just send the response
                orchestrator_msg = Message(
                    role=MessageRole.AGENT,
                    agent_type=AgentType.ORCHESTRATOR,
                    content=response["content"],
                )
                await send_ws_message(websocket, "message", orchestrator_msg.model_dump(mode="json"))
                await save_message_to_db(session_id, "agent", response["content"], "orchestrator")
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
