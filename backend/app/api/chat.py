import asyncio
import json
import uuid
from typing import Any, Annotated

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, CurrentUser
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
from app.services.orchestrator import execute_tool
from app.services.analytics import get_analytics, MetricType, MetricEvent

router = APIRouter(prefix="/chat", tags=["chat"])

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
        .where(ChatMessage.session_id == session_id)
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
) -> None:
    """Save a message to the database using a new session."""
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        message = ChatMessage(
            session_id=session_id,
            role=role,
            agent_type=agent_type,
            content=content,
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


async def get_best_credential_for_agent(user_id: str, agent_name: str) -> SiteCredential | None:
    """
    Get the best available credential for an agent.

    Priority order:
    - visitor_traffic: Placer.ai (people visiting)
    - vehicle_traffic: SiteUSA (VPD - cars)
    - customer_profile: Placer.ai
    - void_analysis: Placer.ai
    - demographics: SiteUSA
    """
    if agent_name in ("visitor_traffic", "customer_profile", "void_analysis"):
        # Placer.ai for visitor traffic, customer profiles, void analysis
        return await get_user_placer_credential(user_id)
    elif agent_name in ("vehicle_traffic", "demographics"):
        # SiteUSA for vehicle traffic (VPD) and demographics
        return await get_user_siteusa_credential(user_id)

    return None


async def handle_tool_calls(
    websocket: WebSocket,
    tool_calls: list[dict],
    session_id: str | None,
    user_id: str,
    conversation_history: list[dict[str, str]],
    user_context: str | None,
    has_placer: bool = False,
    has_siteusa: bool = False,
    document_context: dict | None = None,
    system_prompt_id: str | None = None,
    analysis_type: str | None = None,
) -> None:
    """
    Handle tool calls from Claude's native tool use.

    This function:
    1. Creates workflow UI for user feedback
    2. Executes each tool in parallel (when possible)
    3. Sends results back to Claude for synthesis
    4. Returns the final synthesized response
    """
    print(f"[HANDLE_TOOLS] Starting with {len(tool_calls)} tool calls")
    from app.services.orchestrator import get_orchestrator_response

    # Map tool names to AgentType for UI
    tool_to_agent_type = {
        "business_search": AgentType.TENANT_ROSTER,  # Use tenant roster icon for business search
        "demographics_analysis": AgentType.DEMOGRAPHICS,
        "tenant_roster": AgentType.TENANT_ROSTER,
        "void_analysis": AgentType.VOID_ANALYSIS,
        "visitor_traffic": AgentType.PLACER,
        "vehicle_traffic": AgentType.SITEUSA,
    }

    tool_descriptions = {
        "business_search": "Google Places: Business Search",
        "demographics_analysis": "Census: Demographics",
        "tenant_roster": "Google: Tenant Roster",
        "void_analysis": "AI: Void Analysis",
        "visitor_traffic": "Placer.ai: Visitor Traffic",
        "vehicle_traffic": "SiteUSA: Vehicle Traffic",
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

    # Execute tools in parallel
    async def execute_single_tool(tool_call: dict) -> dict:
        tool_name = tool_call["name"]
        tool_input = tool_call["input"]
        print(f"[HANDLE_TOOLS] Executing tool: {tool_name} with input: {tool_input}")

        # Get credential if needed
        credential = await get_best_credential_for_agent(user_id, tool_name)

        try:
            result = await execute_tool(tool_name, tool_input, user_id, credential)
            print(f"[HANDLE_TOOLS] Tool {tool_name} returned {len(result)} chars")
            return {
                "tool_call_id": tool_call["id"],
                "tool_name": tool_name,
                "result": result,
                "success": True,
            }
        except Exception as e:
            print(f"[HANDLE_TOOLS] Tool {tool_name} ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "tool_call_id": tool_call["id"],
                "tool_name": tool_name,
                "result": f"Error executing {tool_name}: {str(e)}",
                "success": False,
            }

    # Run all tools in parallel
    print(f"[HANDLE_TOOLS] Running {len(tool_calls)} tools in parallel...")
    tool_results = await asyncio.gather(*[execute_single_tool(tc) for tc in tool_calls])
    print(f"[HANDLE_TOOLS] All tools completed, got {len(tool_results)} results")

    # Send results for each tool and update workflow UI
    for result_dict in tool_results:
        tool_name = result_dict["tool_name"]
        result = result_dict["result"]
        tool_call_id = result_dict["tool_call_id"]

        # Send tool result as a message
        agent_type = tool_to_agent_type.get(tool_name, AgentType.ORCHESTRATOR)
        tool_msg = Message(
            role=MessageRole.AGENT,
            agent_type=agent_type,
            content=result,
        )
        await send_ws_message(websocket, "message", tool_msg.model_dump(mode="json"))

        # Save to database
        if session_id:
            await save_message_to_db(session_id, "agent", result, tool_name)

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
        synthesis_response = get_orchestrator_response(
            conversation_history,
            pending_tool_results=pending_results,
            user_context=user_context,
            has_placer_credentials=has_placer,
            has_siteusa_credentials=has_siteusa,
            document_context=document_context,
            system_prompt_id=system_prompt_id,
            analysis_type=analysis_type,
        )

        # Check if Claude wants to use more tools (rare, but possible)
        if synthesis_response.get("tool_calls"):
            # Recursive call for additional tools
            await handle_tool_calls(
                websocket=websocket,
                tool_calls=synthesis_response["tool_calls"],
                session_id=session_id,
                user_id=user_id,
                conversation_history=conversation_history,
                user_context=user_context,
                has_placer=has_placer,
                has_siteusa=has_siteusa,
                document_context=document_context,
                system_prompt_id=system_prompt_id,
                analysis_type=analysis_type,
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
    from app.services.orchestrator import get_orchestrator_response, run_agent_async, generate_conversation_title
    from app.services.places import resolve_business_to_address, extract_business_query_from_message
    from app.api.preferences import build_personalized_context

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
    print(f"WebSocket accepted for session: {session_id} (user: {user_id})")

    try:
        # Load existing conversation history for Claude (only for existing sessions)
        conversation_history: list[dict[str, str]] = []
        doc_context: dict | None = None
        session_prompt_id: str | None = None
        session_analysis_type: str | None = None
        if actual_session_id:
            print(f"Loading history for session: {actual_session_id}")
            conversation_history = await load_session_history(actual_session_id)
            print(f"Loaded {len(conversation_history)} messages")
            # Load document context and prompt info for analysis sessions
            async with async_session_factory() as db:
                result = await db.execute(
                    select(ChatSession).where(ChatSession.id == actual_session_id)
                )
                chat_sess = result.scalar_one_or_none()
                if chat_sess:
                    if chat_sess.document_context:
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

        while True:
            data = await websocket.receive_text()
            try:
                message_data = json.loads(data)
            except json.JSONDecodeError:
                continue
            user_content = message_data.get("content", "")

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
                async with async_session_factory() as db:
                    # Generate title from the first message
                    title = None
                    try:
                        title = generate_conversation_title(user_content)
                    except Exception:
                        pass  # Title generation is non-critical

                    chat_session = ChatSession(
                        user_id=user_id,
                        title=title,
                        system_prompt_id="MASTER_DEFAULT",
                    )
                    db.add(chat_session)
                    await db.commit()
                    await db.refresh(chat_session)
                    actual_session_id = chat_session.id
                    session_prompt_id = "MASTER_DEFAULT"

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
                    title = generate_conversation_title(user_content)
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
                        print(f"Detected business query: {business_query}")
                        # Try to resolve to an address using Google Places
                        resolved = await resolve_business_to_address(business_query)
                        if resolved:
                            business_name, resolved_address = resolved
                            current_address = resolved_address
                            print(f"Resolved to address: {current_address}")

            # Check user credentials for premium data sources
            has_placer = await get_user_placer_credential(user_id) is not None
            has_siteusa = await get_user_siteusa_credential(user_id) is not None

            # Get orchestrator response with native tool calling
            try:
                response = get_orchestrator_response(
                    conversation_history,
                    user_context=user_context,
                    has_placer_credentials=has_placer,
                    has_siteusa_credentials=has_siteusa,
                    document_context=doc_context,
                    system_prompt_id=session_prompt_id,
                    analysis_type=session_analysis_type,
                )
            except Exception as e:
                error_msg = Message(
                    role=MessageRole.SYSTEM,
                    content=f"I'm having trouble connecting to my AI backend. Error: {str(e)}",
                )
                await send_ws_message(websocket, "message", error_msg.model_dump(mode="json"))
                continue

            # Check if Claude wants to use tools
            tool_calls = response.get("tool_calls", [])
            print(f"[CHAT] Response received: {len(tool_calls)} tool_calls, stop_reason={response.get('stop_reason')}")

            if tool_calls:
                print(f"[CHAT] Executing {len(tool_calls)} tool calls...")
                # Claude is requesting to use tools - execute them
                await handle_tool_calls(
                    websocket=websocket,
                    tool_calls=tool_calls,
                    session_id=actual_session_id,
                    user_id=user_id,
                    conversation_history=conversation_history,
                    user_context=user_context,
                    has_placer=has_placer,
                    has_siteusa=has_siteusa,
                    document_context=doc_context,
                    system_prompt_id=session_prompt_id,
                    analysis_type=session_analysis_type,
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

            # Legacy: If orchestrator wants to run agents (backward compatibility)
            tools_to_run = response.get("tools_to_run", [])
            if tools_to_run and current_address and not tool_calls:
                # Create workflow steps
                workflow: list[WorkflowStep] = []
                agent_type_map = {
                    "demographics": AgentType.DEMOGRAPHICS,
                    "tenant_roster": AgentType.TENANT_ROSTER,
                    "visitor_traffic": AgentType.PLACER,  # Placer.ai for visitor/foot traffic
                    "vehicle_traffic": AgentType.SITEUSA,  # SiteUSA for VPD (vehicles per day)
                    "customer_profile": AgentType.PLACER,  # Placer.ai for customer profiles
                    "void_analysis": AgentType.VOID_ANALYSIS,
                }

                # Descriptive labels showing data source and task
                tool_descriptions = {
                    "demographics": "Census: Demographics",
                    "tenant_roster": "Google: Tenant Roster",
                    "visitor_traffic": "Placer.ai: Visitor Traffic",
                    "vehicle_traffic": "SiteUSA: Vehicle Traffic (VPD)",
                    "customer_profile": "Placer.ai: Customer Profile",
                    "void_analysis": "AI: Void Analysis",
                }

                for tool in tools_to_run:
                    if tool in agent_type_map:
                        workflow.append(
                            WorkflowStep(
                                id=str(uuid.uuid4()),
                                agent_type=agent_type_map[tool],
                                description=tool_descriptions.get(tool, tool.replace('_', ' ').title()),
                            )
                        )

                if workflow:
                    # Send workflow init
                    await send_ws_message(
                        websocket,
                        "workflow_init",
                        [step.model_dump(mode="json") for step in workflow],
                    )

                    await asyncio.sleep(0.3)

                    # Check if void_analysis needs data from other agents
                    needs_chaining = "void_analysis" in tools_to_run
                    demographics_data: dict | None = None
                    tenants_data: list[dict] | None = None

                    # Get credentials for browser-based agents
                    browser_agents = ["visitor_traffic", "vehicle_traffic", "demographics", "customer_profile", "void_analysis"]
                    agent_credentials: dict[str, SiteCredential | None] = {}

                    for tool in tools_to_run:
                        if tool in browser_agents:
                            agent_credentials[tool] = await get_best_credential_for_agent(user_id, tool)
                            if agent_credentials[tool]:
                                print(f"Found {agent_credentials[tool].site_name} credential for {tool}")
                            else:
                                print(f"No browser credential for {tool}, will use API fallback")

                    # If void analysis is requested, gather supporting data first
                    if needs_chaining:
                        from app.services.census import get_demographics_structured
                        from app.services.places import get_tenants_structured

                        # Gather demographics data
                        demographics_data = await get_demographics_structured(current_address)

                        # Gather tenant data
                        tenants_data = await get_tenants_structured(current_address)

                    # Separate agents into parallel-safe and sequential
                    # void_analysis needs to run last (depends on other data)
                    parallel_agents = [t for t in tools_to_run if t != "void_analysis"]
                    has_void_analysis = "void_analysis" in tools_to_run

                    # Mark all parallel agents as running
                    for tool in parallel_agents:
                        step = next((s for s in workflow if s.description.lower().replace(" ", "_").replace("running_", "") == tool), None)
                        if step:
                            await send_ws_message(
                                websocket,
                                "workflow_update",
                                {"step_id": step.id, "status": WorkflowStepStatus.RUNNING.value, "agent_type": tool},
                            )

                    # Create tasks for parallel execution
                    async def run_single_agent(tool: str) -> dict:
                        credential = agent_credentials.get(tool)
                        if credential:
                            result = await run_agent_async(
                                tool,
                                current_address,
                                user_id=user_id,
                                credential=credential,
                            )
                        else:
                            result = await run_agent_async(tool, current_address)
                        return {"agent": tool, "result": result}

                    # Run parallel agents concurrently
                    agent_results = []
                    if parallel_agents:
                        parallel_results = await asyncio.gather(
                            *[run_single_agent(tool) for tool in parallel_agents]
                        )
                        agent_results.extend(parallel_results)

                    # Send results for parallel agents
                    for result_dict in agent_results:
                        tool = result_dict["agent"]
                        result = result_dict["result"]

                        # Send agent message
                        agent_msg = Message(
                            role=MessageRole.AGENT,
                            agent_type=agent_type_map.get(tool, AgentType.ORCHESTRATOR),
                            content=result,
                        )
                        await send_ws_message(
                            websocket, "message", agent_msg.model_dump(mode="json")
                        )

                        # Save agent message to database
                        if actual_session_id:
                            await save_message_to_db(
                                actual_session_id, "agent", result, tool
                            )

                        # Mark step as completed
                        step = next((s for s in workflow if s.description.lower().replace(" ", "_").replace("running_", "") == tool), None)
                        if step:
                            await send_ws_message(
                                websocket,
                                "workflow_update",
                                {"step_id": step.id, "status": WorkflowStepStatus.COMPLETED.value},
                            )

                    # Run void_analysis last if requested (depends on other data)
                    if has_void_analysis:
                        void_step = next((s for s in workflow if "void" in s.description.lower()), None)
                        if void_step:
                            await send_ws_message(
                                websocket,
                                "workflow_update",
                                {"step_id": void_step.id, "status": WorkflowStepStatus.RUNNING.value, "agent_type": "void_analysis"},
                            )

                        # Get credential for void analysis (Placer.ai preferred)
                        void_credential = agent_credentials.get("void_analysis")
                        void_result = await run_agent_async(
                            "void_analysis",
                            current_address,
                            user_id=user_id,
                            credential=void_credential,
                            demographics_data=demographics_data,
                            tenants_data=tenants_data,
                        )
                        agent_results.append({"agent": "void_analysis", "result": void_result})

                        # Send void analysis message
                        void_msg = Message(
                            role=MessageRole.AGENT,
                            agent_type=AgentType.VOID_ANALYSIS,
                            content=void_result,
                        )
                        await send_ws_message(
                            websocket, "message", void_msg.model_dump(mode="json")
                        )

                        if actual_session_id:
                            await save_message_to_db(
                                actual_session_id, "agent", void_result, "void_analysis"
                            )

                        if void_step:
                            await send_ws_message(
                                websocket,
                                "workflow_update",
                                {"step_id": void_step.id, "status": WorkflowStepStatus.COMPLETED.value},
                            )

                    # Get orchestrator to synthesize results with personalized context
                    synthesis_response = get_orchestrator_response(
                        conversation_history,
                        pending_tool_results=agent_results,
                        user_context=user_context,
                        system_prompt_id=session_prompt_id,
                        analysis_type=session_analysis_type,
                    )

                    # Send synthesis
                    synthesis_msg = Message(
                        role=MessageRole.AGENT,
                        agent_type=AgentType.ORCHESTRATOR,
                        content=synthesis_response["content"],
                    )
                    await send_ws_message(
                        websocket, "message", synthesis_msg.model_dump(mode="json")
                    )

                    # Save synthesis to database
                    if actual_session_id:
                        await save_message_to_db(
                            actual_session_id, "agent", synthesis_response["content"], "orchestrator"
                        )

                    # Add synthesis to history
                    conversation_history.append({"role": "assistant", "content": synthesis_response["content"]})

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for session: {session_id}")
    except Exception as e:
        import traceback
        print(f"WebSocket error for session {session_id}: {e}")
        traceback.print_exc()
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
        print(f"WebSocket cleanup for session: {session_id} (user: {user_id})")


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
    from app.services.orchestrator import get_orchestrator_response, run_agent_async, generate_conversation_title
    from app.services.places import resolve_business_to_address, extract_business_query_from_message
    from app.api.preferences import build_personalized_context

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

    await websocket.accept()
    connection_key = f"chat:{user_id}"
    active_connections[connection_key] = websocket
    print(f"Chat WebSocket connected for user: {user_id}")

    # Track conversation state per session
    conversation_histories: dict[str, list[dict[str, str]]] = {}
    current_addresses: dict[str, str] = {}
    document_contexts: dict[str, dict | None] = {}
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
                async with async_session_factory() as db:
                    # Generate title from first message
                    title = None
                    try:
                        title = generate_conversation_title(user_content)
                    except Exception:
                        pass

                    chat_session = ChatSession(
                        user_id=user_id,
                        title=title,
                        system_prompt_id="MASTER_DEFAULT",
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
                session_prompt_ids[session_id] = "MASTER_DEFAULT"
                session_analysis_types[session_id] = None

            # Load conversation history and document context if not cached
            if session_id not in conversation_histories:
                conversation_histories[session_id] = await load_session_history(session_id)
                # Load document context and prompt info for analysis sessions
                async with async_session_factory() as db:
                    result = await db.execute(
                        select(ChatSession).where(ChatSession.id == session_id)
                    )
                    chat_sess = result.scalar_one_or_none()
                    if chat_sess:
                        session_prompt_ids[session_id] = chat_sess.system_prompt_id
                        session_analysis_types[session_id] = chat_sess.analysis_type
                        if chat_sess.document_context:
                            document_contexts[session_id] = chat_sess.document_context
                            # Pre-set address from document context
                            addr = chat_sess.document_context.get("property_address")
                            if addr:
                                current_addresses[session_id] = addr
                        else:
                            document_contexts[session_id] = None
                    else:
                        document_contexts[session_id] = None
                        session_prompt_ids[session_id] = None
                        session_analysis_types[session_id] = None

            conversation_history = conversation_histories[session_id]
            current_address = current_addresses.get(session_id)
            doc_context = document_contexts.get(session_id)
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

            # Check user credentials for premium data sources
            has_placer = await get_user_placer_credential(user_id) is not None
            has_siteusa = await get_user_siteusa_credential(user_id) is not None

            # Get orchestrator response (with document context and prompt ID for analysis sessions)
            try:
                response = get_orchestrator_response(
                    conversation_history,
                    user_context=user_context,
                    has_placer_credentials=has_placer,
                    has_siteusa_credentials=has_siteusa,
                    document_context=doc_context,
                    system_prompt_id=s_prompt_id,
                    analysis_type=s_analysis_type,
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
            print(f"[CHAT-WS] Response: {len(tool_calls)} tool_calls, {len(response.get('content', ''))} chars text")

            if tool_calls:
                print(f"[CHAT-WS] Executing {len(tool_calls)} tool calls...")
                # Claude is requesting to use tools - execute them
                await handle_tool_calls(
                    websocket=websocket,
                    tool_calls=tool_calls,
                    session_id=session_id,
                    user_id=user_id,
                    conversation_history=conversation_history,
                    user_context=user_context,
                    has_placer=has_placer,
                    has_siteusa=has_siteusa,
                    document_context=doc_context,
                    system_prompt_id=s_prompt_id,
                    analysis_type=s_analysis_type,
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

            # Legacy: Run agents if needed (backward compatibility)
            tools_to_run = response.get("tools_to_run", [])
            if tools_to_run and current_address and not tool_calls:
                await run_agent_workflow(
                    websocket=websocket,
                    session_id=session_id,
                    tools_to_run=tools_to_run,
                    current_address=current_address,
                    user_id=user_id,
                    conversation_history=conversation_history,
                    user_context=user_context,
                    system_prompt_id=s_prompt_id,
                    analysis_type=s_analysis_type,
                )

    except WebSocketDisconnect:
        print(f"Chat WebSocket disconnected for user: {user_id}")
    except Exception as e:
        import traceback
        print(f"Chat WebSocket error for user {user_id}: {e}")
        traceback.print_exc()
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
        print(f"Chat WebSocket cleanup for user: {user_id}")


async def run_agent_workflow(
    websocket: WebSocket,
    session_id: str,
    tools_to_run: list[str],
    current_address: str,
    user_id: str,
    conversation_history: list[dict[str, str]],
    user_context: str | None,
    system_prompt_id: str | None = None,
    analysis_type: str | None = None,
) -> None:
    """Run agent workflow and send updates to WebSocket."""
    from app.services.orchestrator import run_agent_async, get_orchestrator_response

    # Create workflow steps
    workflow: list[WorkflowStep] = []
    agent_type_map = {
        "demographics": AgentType.DEMOGRAPHICS,
        "tenant_roster": AgentType.TENANT_ROSTER,
        "visitor_traffic": AgentType.PLACER,  # Placer.ai for visitor/foot traffic
        "vehicle_traffic": AgentType.SITEUSA,  # SiteUSA for VPD (vehicles per day)
        "customer_profile": AgentType.PLACER,  # Placer.ai for customer profiles
        "void_analysis": AgentType.VOID_ANALYSIS,
    }

    # Descriptive labels showing data source and task
    tool_descriptions = {
        "demographics": "Census: Demographics",
        "tenant_roster": "Google: Tenant Roster",
        "visitor_traffic": "Placer.ai: Visitor Traffic",
        "vehicle_traffic": "SiteUSA: Vehicle Traffic (VPD)",
        "customer_profile": "Placer.ai: Customer Profile",
        "void_analysis": "AI: Void Analysis",
    }

    for tool in tools_to_run:
        if tool in agent_type_map:
            workflow.append(
                WorkflowStep(
                    id=str(uuid.uuid4()),
                    agent_type=agent_type_map[tool],
                    description=tool_descriptions.get(tool, tool.replace('_', ' ').title()),
                )
            )

    if not workflow:
        return

    # Send workflow init
    await send_ws_message(
        websocket,
        "workflow_init",
        [step.model_dump(mode="json") for step in workflow],
    )

    await asyncio.sleep(0.3)

    # Check for void analysis chaining
    needs_chaining = "void_analysis" in tools_to_run
    demographics_data: dict | None = None
    tenants_data: list[dict] | None = None

    # Get credentials for browser-based agents
    # Each agent type may have different credential preferences
    browser_agents = ["foot_traffic", "demographics", "customer_profile", "void_analysis"]
    agent_credentials: dict[str, SiteCredential | None] = {}

    for tool in tools_to_run:
        if tool in browser_agents:
            agent_credentials[tool] = await get_best_credential_for_agent(user_id, tool)
            if agent_credentials[tool]:
                print(f"Found {agent_credentials[tool].site_name} credential for {tool}")
            else:
                print(f"No browser credential for {tool}, will use API fallback")

    # Gather supporting data for void analysis
    if needs_chaining:
        from app.services.census import get_demographics_structured
        from app.services.places import get_tenants_structured
        demographics_data = await get_demographics_structured(current_address)
        tenants_data = await get_tenants_structured(current_address)

    # Run parallel agents
    parallel_agents = [t for t in tools_to_run if t != "void_analysis"]
    has_void_analysis = "void_analysis" in tools_to_run

    # Mark parallel agents as running
    for tool in parallel_agents:
        step = next((s for s in workflow if tool.replace("_", " ").title() in s.description), None)
        if step:
            await send_ws_message(
                websocket,
                "workflow_update",
                {"step_id": step.id, "status": WorkflowStepStatus.RUNNING.value, "agent_type": tool},
            )

    # Run agents
    async def run_single_agent(tool: str) -> dict:
        credential = agent_credentials.get(tool)
        if credential:
            result = await run_agent_async(tool, current_address, user_id=user_id, credential=credential)
        else:
            result = await run_agent_async(tool, current_address)
        return {"agent": tool, "result": result}

    agent_results = []
    if parallel_agents:
        parallel_results = await asyncio.gather(*[run_single_agent(tool) for tool in parallel_agents])
        agent_results.extend(parallel_results)

    # Send results for parallel agents
    for result_dict in agent_results:
        tool = result_dict["agent"]
        result = result_dict["result"]

        agent_msg = Message(
            role=MessageRole.AGENT,
            agent_type=agent_type_map.get(tool, AgentType.ORCHESTRATOR),
            content=result,
        )
        await send_ws_message(websocket, "message", agent_msg.model_dump(mode="json"))
        await save_message_to_db(session_id, "agent", result, tool)

        step = next((s for s in workflow if tool.replace("_", " ").title() in s.description), None)
        if step:
            await send_ws_message(
                websocket,
                "workflow_update",
                {"step_id": step.id, "status": WorkflowStepStatus.COMPLETED.value},
            )

    # Run void analysis last
    if has_void_analysis:
        void_step = next((s for s in workflow if "void" in s.description.lower()), None)
        if void_step:
            await send_ws_message(
                websocket,
                "workflow_update",
                {"step_id": void_step.id, "status": WorkflowStepStatus.RUNNING.value, "agent_type": "void_analysis"},
            )

        # Get credential for void analysis (Placer.ai preferred)
        void_credential = agent_credentials.get("void_analysis")
        void_result = await run_agent_async(
            "void_analysis",
            current_address,
            user_id=user_id,
            credential=void_credential,
            demographics_data=demographics_data,
            tenants_data=tenants_data,
        )
        agent_results.append({"agent": "void_analysis", "result": void_result})

        void_msg = Message(
            role=MessageRole.AGENT,
            agent_type=AgentType.VOID_ANALYSIS,
            content=void_result,
        )
        await send_ws_message(websocket, "message", void_msg.model_dump(mode="json"))
        await save_message_to_db(session_id, "agent", void_result, "void_analysis")

        if void_step:
            await send_ws_message(
                websocket,
                "workflow_update",
                {"step_id": void_step.id, "status": WorkflowStepStatus.COMPLETED.value},
            )

    # Synthesize results
    synthesis_response = get_orchestrator_response(
        conversation_history,
        pending_tool_results=agent_results,
        user_context=user_context,
        system_prompt_id=system_prompt_id,
        analysis_type=analysis_type,
    )

    synthesis_msg = Message(
        role=MessageRole.AGENT,
        agent_type=AgentType.ORCHESTRATOR,
        content=synthesis_response["content"],
    )
    await send_ws_message(websocket, "message", synthesis_msg.model_dump(mode="json"))
    await save_message_to_db(session_id, "agent", synthesis_response["content"], "orchestrator")
    conversation_history.append({"role": "assistant", "content": synthesis_response["content"]})
