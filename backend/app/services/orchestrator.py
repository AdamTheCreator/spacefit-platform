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


def get_orchestrator_response(
    messages: list[dict[str, str]],
    pending_tool_results: list[dict] | None = None,
    user_context: str | None = None,
    has_placer_credentials: bool = False,
    has_siteusa_credentials: bool = False,
    has_costar_credentials: bool = False,
) -> dict:
    """
    Get a response from the orchestrator using Claude's native tool calling.

    Args:
        messages: Conversation history in Claude format
        pending_tool_results: Results from previously executed tools
        user_context: Personalized context string from user preferences
        has_*_credentials: Flags indicating which premium data sources are available

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

    # Build the full system prompt with user context
    full_system_prompt = SYSTEM_PROMPT
    if user_context:
        full_system_prompt = SYSTEM_PROMPT + "\n\n" + user_context

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
