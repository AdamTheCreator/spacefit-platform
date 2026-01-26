"""
SpaceFit AI Orchestrator Service

Uses Claude's native tool calling to coordinate specialized agents.
This replaces keyword-matching with structured tool use for reliable data retrieval.
"""

from anthropic import Anthropic
from anthropic.types import Message, ToolUseBlock, TextBlock
from app.core.config import settings
from app.services.tools import (
    SPACEFIT_TOOLS,
    get_tools_for_context,
    should_force_tool_use,
)
from app.services.prompt_registry import (
    get_system_prompt_for_session,
    format_document_context_block,
    DEFAULT_PROMPT_ID,
    VOID_ANALYSIS_PROMPT_ID,
)

# Initialize the Anthropic client
client = Anthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """You are the SpaceFit AI assistant, an expert in commercial real estate analysis for shopping malls and retail centers.

Your role is to help users analyze properties and find business information by:
1. Understanding what property or location they want to analyze
2. Using the appropriate tools to gather REAL data
3. Synthesizing findings into actionable insights

CRITICAL RULES:

1. **ALWAYS USE TOOLS FOR FACTUAL DATA**: When users ask about businesses, locations, demographics, or any real-world data, you MUST use the appropriate tool. NEVER answer from memory or training data.

2. **Business/Location Queries**: For ANY question about what businesses exist in an area (coffee shops, restaurants, stores, etc.), use the `business_search` tool. Do not guess or make up business names and addresses.

3. **Property Analysis**: For property analysis requests, use the appropriate combination of tools:
   - demographics_analysis for trade area demographics
   - tenant_roster for current tenants at a property
   - void_analysis for identifying opportunities
   - visitor_traffic for foot traffic data
   - vehicle_traffic for VPD data

4. **Be Honest About Limitations**: If a tool returns no results or an error, tell the user honestly. Never fabricate data to fill gaps.

5. **Cite Sources**: When presenting data from tools, mention the source (e.g., "According to Google Places...", "Census data shows...").

RESPONSE STYLE:
- Keep responses concise and conversational
- Use bullet points for data presentation
- Focus on insights and actionable information
- If you need more information from the user, ask specific questions"""


def build_void_analysis_system_prompt(document_context: dict) -> str:
    """
    Build a specialized system prompt for void analysis sessions
    that are pre-seeded with document context.
    """
    property_name = document_context.get("property_name", "Unknown Property")
    property_address = document_context.get("property_address", "Unknown Address")
    existing_tenants = document_context.get("existing_tenants", [])
    available_spaces = document_context.get("available_spaces", [])
    property_info = document_context.get("property_info", {})
    trade_area_miles = document_context.get("trade_area_miles", 3.0)
    notes = document_context.get("notes")
    doc_type = document_context.get("document_type", "leasing_flyer")

    # Format tenants list
    tenant_lines = []
    for t in existing_tenants:
        name = t.get("name", "Unknown")
        cat = t.get("category", "")
        sf = t.get("square_footage")
        anchor = " (Anchor)" if t.get("is_anchor") else ""
        line = f"  - {name}{anchor}"
        if cat:
            line += f" [{cat}]"
        if sf:
            line += f" — {sf:,} SF"
        tenant_lines.append(line)

    # Format available spaces
    space_lines = []
    for s in available_spaces:
        suite = s.get("suite_number") or s.get("name", "Space")
        sf = s.get("square_footage")
        rent = s.get("asking_rent_psf")
        line = f"  - {suite}"
        if sf:
            line += f" — {sf:,} SF"
        if rent:
            line += f" @ ${rent}/SF"
        endcap = " (Endcap)" if s.get("is_endcap") else ""
        drive_thru = " (Drive-Thru)" if s.get("has_drive_thru") else ""
        line += endcap + drive_thru
        space_lines.append(line)

    # Property summary
    total_sf = property_info.get("total_sf", "")
    prop_type = property_info.get("property_type", "")

    prompt = f"""You are the SpaceFit AI Void Analysis Agent, an expert in commercial real estate tenant mix optimization.

You are analyzing a property based on data extracted from an uploaded {doc_type.replace('_', ' ')}. Your goal is to perform a comprehensive void analysis and identify the best tenant categories and specific tenants to fill available spaces.

## PROPERTY CONTEXT (pre-loaded from document)

**Property:** {property_name}
**Address:** {property_address}
{f'**Total SF:** {total_sf:,}' if total_sf else ''}
{f'**Type:** {prop_type}' if prop_type else ''}
**Trade Area:** {trade_area_miles} mile radius

**Existing Tenants ({len(existing_tenants)}):**
{chr(10).join(tenant_lines) if tenant_lines else '  (none extracted)'}

**Available Spaces ({len(available_spaces)}):**
{chr(10).join(space_lines) if space_lines else '  (none extracted)'}

{f'**User Notes:** {notes}' if notes else ''}

## YOUR TASK

You already have the property details above. Proceed immediately with the analysis — do NOT ask the user to re-enter property information.

1. **Acknowledge** the property and summarize what you see (briefly — 2-3 sentences).
2. **Use tools** to gather supporting data:
   - `demographics_analysis` for trade area demographics at the property address
   - `business_search` to find nearby competitors and complementary businesses
   - `void_analysis` to identify category gaps
   - `visitor_traffic` for foot traffic data (if credentials available)
   - `vehicle_traffic` for VPD data (if credentials available)
3. **Synthesize** findings into a void analysis report with:
   - Executive summary
   - Category gap analysis (what's missing vs. what's present)
   - Top 5 recommended tenant categories with rationale
   - Specific tenant suggestions for each available space
   - Competitive context (nearby centers, overlap)
   - Risk factors and considerations

## QUESTION POLICY

- If the property address is clear, do NOT ask for it again — proceed directly.
- If critical info is ambiguous (e.g., the address couldn't be parsed), ask ONE targeted question.
- Prefer action over clarification. The user expects you to start working immediately.

## RESPONSE STYLE
- Lead with action, not questions
- Use structured headings and bullet points
- Be specific about tenant recommendations (name actual brands/concepts)
- Cite data sources when presenting findings
- Keep the tone professional but direct"""

    return prompt


def get_orchestrator_response(
    messages: list[dict[str, str]],
    pending_tool_results: list[dict] | None = None,
    user_context: str | None = None,
    has_placer_credentials: bool = False,
    has_siteusa_credentials: bool = False,
    has_costar_credentials: bool = False,
    document_context: dict | None = None,
    system_prompt_id: str | None = None,
    analysis_type: str | None = None,
) -> dict:
    """
    Get a response from the orchestrator using Claude's native tool calling.

    Args:
        messages: Conversation history in Claude format
        pending_tool_results: Results from previously executed tools
        user_context: Personalized context string from user preferences
        has_*_credentials: Flags indicating which premium data sources are available
        document_context: Extracted document data for analysis sessions
        system_prompt_id: Explicit prompt ID from the session's system_prompt_id field
        analysis_type: Session analysis_type for fallback prompt resolution

    Returns:
        dict with:
        - 'content': Response text
        - 'tool_calls': List of tools Claude wants to use (if any)
        - 'stop_reason': Why Claude stopped (end_turn, tool_use, etc.)
    """
    # Add any pending tool results to the conversation
    # When we have tool results, we need to add them as a new user message
    # asking Claude to synthesize the findings
    if pending_tool_results:
        results_text = "Here are the results from the data sources I searched:\n\n" + "\n\n---\n\n".join([
            f"**{r['tool_name']} Results:**\n{r['result']}"
            for r in pending_tool_results
        ])
        results_text += "\n\nPlease summarize these findings for me in a helpful, conversational way. Include the key details like names, addresses, and ratings."
        messages = messages + [{"role": "user", "content": results_text}]
        # Don't force tool use for synthesis - just let Claude respond naturally
        print(f"[ORCHESTRATOR] Added tool results to conversation for synthesis")

    # --- System prompt selection via Prompt Registry ---
    # Resolve the prompt: explicit ID > analysis_type inference > default.
    # For backward compat, if no system_prompt_id but document_context exists,
    # infer void analysis.
    effective_prompt_id = system_prompt_id
    effective_analysis_type = analysis_type
    if not effective_prompt_id and document_context:
        effective_prompt_id = VOID_ANALYSIS_PROMPT_ID
        effective_analysis_type = "void_analysis"

    prompt_def = get_system_prompt_for_session(effective_prompt_id, effective_analysis_type)
    full_system_prompt = prompt_def.content
    print(f"[ORCHESTRATOR] Using prompt: {prompt_def.prompt_id} (v{prompt_def.version})")

    # Inject document context as a structured block after the system prompt
    if document_context:
        context_block = format_document_context_block(document_context)
        if context_block:
            full_system_prompt = full_system_prompt + "\n\n" + context_block

    if user_context:
        full_system_prompt = full_system_prompt + "\n\n" + user_context

    # Get available tools based on user credentials
    tools = get_tools_for_context(
        has_placer_credentials=has_placer_credentials,
        has_siteusa_credentials=has_siteusa_credentials,
        has_costar_credentials=has_costar_credentials,
    )

    # Determine if we should force tool use for this query
    # Don't force tool use if we already have tool results (synthesis phase)
    tool_choice: dict | None = None

    if not pending_tool_results:
        last_user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    last_user_message = content
                    break

        if should_force_tool_use(last_user_message):
            # Force Claude to use at least one tool for factual queries
            tool_choice = {"type": "any"}
            print(f"[ORCHESTRATOR] Forcing tool use for query: {last_user_message[:50]}...")

    print(f"[ORCHESTRATOR] Calling Claude with {len(tools)} tools, tool_choice={tool_choice}")

    # Call Claude with tools
    # Build kwargs - only include tool_choice if it's set (not None)
    create_kwargs = {
        "model": settings.anthropic_model,
        "max_tokens": 2048,
        "system": full_system_prompt,
        "messages": messages,
        "tools": tools,
    }
    if tool_choice is not None:
        create_kwargs["tool_choice"] = tool_choice

    response = client.messages.create(**create_kwargs)

    # Parse the response
    text_content = ""
    tool_calls = []

    print(f"[ORCHESTRATOR] Response stop_reason: {response.stop_reason}")

    for block in response.content:
        if isinstance(block, TextBlock):
            text_content += block.text
        elif isinstance(block, ToolUseBlock):
            print(f"[ORCHESTRATOR] Tool call detected: {block.name} with input {block.input}")
            tool_calls.append({
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })

    print(f"[ORCHESTRATOR] Returning: {len(tool_calls)} tool_calls, {len(text_content)} chars text")

    return {
        "content": text_content,
        "tool_calls": tool_calls,
        "stop_reason": response.stop_reason,
    }


async def execute_tool(tool_name: str, tool_input: dict, user_id: str | None = None, credential=None) -> str:
    """
    Execute a tool and return the result.

    Args:
        tool_name: Name of the tool to execute
        tool_input: Input parameters for the tool
        user_id: Optional user ID for credential lookup
        credential: Optional pre-fetched credential

    Returns:
        String result from the tool execution
    """
    if tool_name == "business_search":
        from app.services.business_search import search_businesses

        result = await search_businesses(
            query=tool_input.get("query"),
            business_type=tool_input.get("business_type"),
            location=tool_input.get("location"),
            radius_miles=tool_input.get("radius_miles", 2.0),
        )
        return result.to_formatted_report()

    elif tool_name == "demographics_analysis":
        from app.services.census import analyze_demographics

        address = tool_input.get("address", "")
        return await analyze_demographics(address)

    elif tool_name == "tenant_roster":
        from app.services.places import analyze_tenant_roster

        address = tool_input.get("address", "")
        return await analyze_tenant_roster(address)

    elif tool_name == "void_analysis":
        from app.agents.void_analysis import generate_void_report
        from app.services.census import get_demographics_structured
        from app.services.places import get_tenants_structured

        address = tool_input.get("address", "")

        # Gather supporting data for void analysis
        demographics_data = await get_demographics_structured(address)
        tenants_data = await get_tenants_structured(address)

        return await generate_void_report(
            property_address=address,
            existing_tenants=tenants_data,
            demographics=demographics_data,
        )

    elif tool_name == "visitor_traffic":
        # Requires Placer.ai credentials
        if credential and credential.site_name.lower() == "placer":
            from app.agents.placer_ai import PlacerAIFootTrafficAgent

            address = tool_input.get("address", "")
            agent = PlacerAIFootTrafficAgent()
            result = await agent.execute(
                "visitor_traffic",
                {
                    "address": address,
                    "user_id": user_id,
                    "credential": credential,
                },
            )
            return result.content

        return "Visitor traffic data requires Placer.ai credentials. Please add your Placer.ai credentials in the Connections settings."

    elif tool_name == "vehicle_traffic":
        # Requires SiteUSA credentials
        if credential and credential.site_name.lower() == "siteusa":
            from app.agents.siteusa_demographics import SiteUSAVehicleTrafficAgent

            address = tool_input.get("address", "")
            agent = SiteUSAVehicleTrafficAgent()
            result = await agent.execute(
                "vehicle_traffic",
                {
                    "address": address,
                    "user_id": user_id,
                    "credential": credential,
                },
            )
            return result.content

        return "Vehicle traffic (VPD) data requires SiteUSA credentials. Please add your SiteUSA credentials in the Connections settings."

    else:
        return f"Unknown tool: {tool_name}"


def generate_conversation_title(first_message: str) -> str:
    """
    Generate a short, descriptive title for a conversation based on the first message.
    Uses Claude to extract the location/property and create a descriptive title.
    """
    try:
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=50,
            system="""Generate a very short title (3-6 words) for a commercial real estate conversation.
IMPORTANT: If a location, address, property name, mall name, or city is mentioned, INCLUDE IT in the title.
Examples:
- "Void analysis for Westfield Mall" -> "Westfield Mall Void Analysis"
- "demographics for 123 Main St" -> "123 Main St Demographics"
- "coffee shops in Westport CT" -> "Westport CT Coffee Shops"
- "foot traffic in downtown Boston" -> "Downtown Boston Foot Traffic"
- "analyze mall property" -> "Mall Property Analysis"
Reply with only the title, no quotes or punctuation.""",
            messages=[{"role": "user", "content": f"First message: {first_message}"}],
        )
        title = response.content[0].text.strip()
        # Ensure title isn't too long
        if len(title) > 60:
            title = title[:57] + "..."
        return title
    except Exception:
        # Fallback: use first few words of the message
        words = first_message.split()[:6]
        return " ".join(words) + ("..." if len(first_message.split()) > 6 else "")


# === Legacy functions for backward compatibility ===
# These will be removed once chat.py is fully migrated

AGENT_SIMULATIONS = {
    "demographics": lambda address: f"Demographics data for {address} - use new tool calling instead",
    "tenant_roster": lambda address: f"Tenant data for {address} - use new tool calling instead",
    "visitor_traffic": lambda address: f"Visitor traffic for {address} - use new tool calling instead",
    "vehicle_traffic": lambda address: f"Vehicle traffic for {address} - use new tool calling instead",
    "void_analysis": lambda address: f"Void analysis for {address} - use new tool calling instead",
}


def run_agent(agent_name: str, address: str) -> str:
    """Legacy sync function - use execute_tool instead."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        execute_tool(agent_name, {"address": address})
    )


async def run_agent_async(
    agent_name: str,
    address: str,
    user_id: str | None = None,
    credential=None,
    progress_callback=None,
    demographics_data: dict | None = None,
    tenants_data: list[dict] | None = None,
) -> str:
    """Legacy async function - use execute_tool instead."""
    # Map old agent names to new tool names
    tool_mapping = {
        "demographics": "demographics_analysis",
        "tenant_roster": "tenant_roster",
        "visitor_traffic": "visitor_traffic",
        "vehicle_traffic": "vehicle_traffic",
        "void_analysis": "void_analysis",
        "customer_profile": "visitor_traffic",  # Map to visitor_traffic
    }

    tool_name = tool_mapping.get(agent_name, agent_name)
    tool_input = {"address": address}

    # Special handling for void_analysis with pre-fetched data
    if agent_name == "void_analysis" and (demographics_data or tenants_data):
        from app.agents.void_analysis import generate_void_report
        return await generate_void_report(
            property_address=address,
            existing_tenants=tenants_data,
            demographics=demographics_data,
        )

    return await execute_tool(tool_name, tool_input, user_id, credential)


def is_browser_based_agent(agent_name: str, credential=None) -> bool:
    """Check if an agent requires browser automation."""
    if credential:
        site = credential.site_name.lower()
        if site in ("placer", "siteusa", "costar"):
            return True
    return False


def get_agent_typical_duration(agent_name: str, credential=None) -> int:
    """Get the typical duration in seconds for an agent."""
    base_durations = {
        "demographics_analysis": 5,
        "demographics": 5,
        "tenant_roster": 3,
        "business_search": 3,
        "void_analysis": 8,
        "visitor_traffic": 2,
        "vehicle_traffic": 2,
    }

    if credential:
        # Browser-based agents take longer
        return 45

    return base_durations.get(agent_name, 5)
