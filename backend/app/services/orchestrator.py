"""
SpaceFit AI Orchestrator Service

Uses Claude to have natural conversations about mall analysis,
coordinating specialized agents to gather and analyze data.
"""

from anthropic import Anthropic
from app.core.config import settings

# Initialize the Anthropic client
client = Anthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """You are the SpaceFit AI assistant, an expert in commercial real estate analysis for shopping malls and retail centers.

Your role is to help users analyze properties by:
1. Understanding what property they want to analyze (get the address/name)
2. Understanding their goals (void analysis, tenant mix review, market assessment, etc.)
3. Coordinating specialized agents to gather data
4. Synthesizing findings into actionable insights

You have access to the following specialized agents (tools):
- **Demographics Agent**: Analyzes Census ACS data for trade area demographics (population, income, age, etc.)
- **Trade Data Agent**: Analyzes BLS QCEW employment data for the area
- **Tenant Roster Agent**: Gets current tenant list from paid data sources (Placer.ai, SafeGraph)
- **Foot Traffic Agent**: Gets foot traffic patterns and visitor demographics from SitesUSA
- **Void Analyzer**: Identifies missing tenant categories based on market potential vs current mix
- **Notification Agent**: Can notify relevant clients about opportunities via email/LinkedIn

CRITICAL RULES FOR RESPONDING:

1. **NEVER FABRICATE DATA**: Do not make up statistics, numbers, visitor counts, demographics, or any other data. Only present data that comes from agent results.

2. **Brief confirmations before analysis**: When you're about to run agents, give a SHORT confirmation like "Let me check the foot traffic data for that location." Do NOT include fake statistics or analysis in this message - just confirm what you're about to do.

3. **Synthesis after agents complete**: When you receive [Agent Results], synthesize and present that REAL data. This is when you provide the detailed analysis with actual numbers.

LOCATION HANDLING:
- Be careful with similar town names (Weston vs Westport, Greenwich vs Greenville). Confirm if unclear.
- For general areas like "downtown Westport", the system can look up data by town/ZIP code. You don't always need a specific street address.
- If the user mentions a business name, the system can resolve it to an address automatically.

RESPONSE STYLE:
- Keep responses concise and conversational
- Use bullet points for data presentation
- Don't repeat the same information twice
- When synthesizing agent results, focus on insights and key takeaways"""


def get_orchestrator_response(
    messages: list[dict[str, str]],
    pending_tool_results: list[dict] | None = None,
    user_context: str | None = None,
) -> dict:
    """
    Get a response from the orchestrator.

    Args:
        messages: Conversation history in Claude format [{"role": "user/assistant", "content": "..."}]
        pending_tool_results: Results from agent executions to incorporate
        user_context: Personalized context string from user preferences

    Returns:
        dict with 'content' (response text) and optionally 'tools_to_run' (list of agent names)
    """
    # Add any pending tool results to the conversation
    if pending_tool_results:
        # Format tool results as a system message
        results_text = "\n\n".join([
            f"**{r['agent']} Results:**\n{r['result']}"
            for r in pending_tool_results
        ])
        messages = messages + [{"role": "user", "content": f"[Agent Results]\n{results_text}"}]

    # Build the full system prompt with user context
    full_system_prompt = SYSTEM_PROMPT
    if user_context:
        full_system_prompt = SYSTEM_PROMPT + user_context

    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        system=full_system_prompt,
        messages=messages,
    )

    response_text = response.content[0].text

    # Check if the response indicates we should run agents
    # For now, we'll use keyword detection - in the future, we could use tool_use
    tools_to_run = []

    response_lower = response_text.lower()

    # Also check the user's last message for explicit analysis requests
    user_message_lower = ""
    if messages:
        last_user_msg = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"),
            ""
        )
        user_message_lower = last_user_msg.lower()

    # Detect if Claude wants to run analysis OR user explicitly requested it
    claude_wants_analysis = any(phrase in response_lower for phrase in [
        "let me analyze",
        "i'll gather",
        "running the",
        "let me check",
        "i'll pull",
        "let me get",
        "i'll run",
        "i will run",
        "let me run",
    ])

    user_requested_analysis = any(phrase in user_message_lower for phrase in [
        "run a void analysis",
        "run void analysis",
        "please run",
        "analyze this property",
        "analyze the property",
        "start analysis",
        "run analysis",
        "identify tenant",
        "identify potential tenant",
    ])

    if claude_wants_analysis or user_requested_analysis:
        # Determine which agents to run based on context (check both response and user message)
        combined_context = response_lower + " " + user_message_lower

        if any(word in combined_context for word in ["demographic", "population", "income", "census"]):
            tools_to_run.append("demographics")
        if any(word in combined_context for word in ["tenant", "roster", "store", "business"]):
            tools_to_run.append("tenant_roster")
        if any(word in combined_context for word in ["traffic", "visitor", "footfall", "vpd", "vehicle"]):
            # Add both visitor traffic (Placer.ai) and vehicle traffic (SiteUSA VPD)
            tools_to_run.append("visitor_traffic")
            tools_to_run.append("vehicle_traffic")
        if any(word in combined_context for word in ["void", "gap", "missing", "opportunity"]):
            tools_to_run.append("void_analysis")
        if any(phrase in combined_context for phrase in ["customer profile", "who shops", "visitor profile", "audience", "shopper"]):
            tools_to_run.append("customer_profile")

        # Outreach detection - for email campaigns after void analysis
        if any(phrase in combined_context for phrase in [
            "outreach", "email", "reach out", "send email", "contact tenant",
            "blast", "mail merge", "campaign", "notify tenant"
        ]):
            tools_to_run.append("outreach")

        # If user explicitly requested void analysis but no specific agents detected, run void analysis
        if not tools_to_run and "void" in user_message_lower:
            tools_to_run.append("void_analysis")

    return {
        "content": response_text,
        "tools_to_run": tools_to_run,
    }


# Simulated agent responses (will be replaced with real data later)
AGENT_SIMULATIONS = {
    "demographics": lambda address: f"""**Trade Area Demographics (5-mile radius around {address})**

- **Population**: 156,432 residents
- **Households**: 58,234
- **Median Household Income**: $82,450
- **Age Distribution**:
  - Under 18: 22%
  - 18-34: 28%
  - 35-54: 31%
  - 55+: 19%
- **Education**: 42% Bachelor's degree or higher
- **Employment Rate**: 94.2%
- **Housing**: 68% owner-occupied

*Key Insight*: Strong middle-to-upper income demographic with high employment. Good mix of families and young professionals.""",

    "tenant_roster": lambda address: f"""**Current Tenant Roster for {address}**

**Anchors (3)**:
- Target (127,000 sq ft)
- Best Buy (45,000 sq ft)
- Marshalls (28,000 sq ft)

**Dining (12)**:
- Chili's, Panera Bread, Chipotle, Starbucks (x2), Panda Express,
- Subway, Jersey Mike's, Five Guys, Buffalo Wild Wings, Smoothie King, Dunkin'

**Retail (18)**:
- Bath & Body Works, Ulta Beauty, GameStop, Shoe Carnival,
- T-Mobile, AT&T, Verizon, Sprint, PetSmart, Michael's,
- Old Navy, Ross, HomeGoods, TJ Maxx, Sally Beauty,
- GNC, Vitamin Shoppe, Kay Jewelers

**Services (8)**:
- Great Clips, Sport Clips, Massage Envy, European Wax Center,
- H&R Block, Edward Jones, State Farm, Allstate

**Vacant (4 spaces)**:
- 2,400 sq ft (former Payless)
- 3,800 sq ft (former Pier 1)
- 1,200 sq ft (inline)
- 5,500 sq ft (endcap)

*Current Occupancy*: 91% (4 vacancies)""",

    "visitor_traffic": lambda address: f"""**Visitor Traffic Analysis for {address}** (Placer.ai)

**Monthly Visitors**: 285,000 average
**Peak Days**: Saturday (52,000), Sunday (48,000)
**Peak Hours**: 12-2 PM, 5-7 PM

**Year-over-Year Trend**: +8.2% growth
**Dwell Time**: 47 minutes average

**Visitor Demographics**:
- 62% Female, 38% Male
- Top age groups: 25-34 (28%), 35-44 (24%)
- 71% within 10-mile radius
- Median HH income of visitors: $76,000

**Top Traffic Drivers**:
1. Target (38% of total traffic)
2. Best Buy (15%)
3. Dining cluster (22%)

*Key Insight*: Strong weekend traffic with solid weekday lunch rush. Growing YoY traffic indicates healthy center.""",

    "vehicle_traffic": lambda address: f"""**Vehicle Traffic Analysis for {address}** (SiteUSA VPD)

**Vehicles Per Day (VPD)**:
- Primary Road: 28,500 VPD
- Secondary Road: 12,200 VPD
- Intersection: 18,400 VPD

**Traffic Patterns**:
- Morning Peak (7-9 AM): 4,200 vehicles/hr
- Lunch Peak (11 AM-1 PM): 3,100 vehicles/hr
- Evening Peak (5-7 PM): 4,800 vehicles/hr

**Year-over-Year Trend**: +3.5% growth
**Weekend vs Weekday**: 15% higher on weekends

**Access Points**:
- Main entrance: Good visibility, right turn only
- Secondary entrance: Full access, lower visibility
- Traffic light at main intersection

*Key Insight*: Strong vehicle counts support retail viability. Evening peak aligns with commuter patterns.""",

    "trade_data": lambda address: f"""**Trade Area Employment Data (BLS QCEW)**

**Employment by Sector** (5-mile radius):
- Retail Trade: 12,450 jobs (+3.2% YoY)
- Health Care: 18,200 jobs (+5.1% YoY)
- Professional Services: 8,900 jobs (+2.8% YoY)
- Accommodation & Food: 9,100 jobs (+4.5% YoY)
- Finance & Insurance: 4,200 jobs (+1.9% YoY)

**Average Weekly Wage**: $1,245
**Unemployment Rate**: 3.8%

**Major Employers Nearby**:
- Regional Medical Center (4,200 employees)
- Corporate Tech Park (2,800 employees)
- University Campus (1,900 employees)

*Key Insight*: Diverse employment base with growth in healthcare and professional services. Strong daytime population for lunch traffic.""",

    "void_analysis": lambda address: f"""**Void Analysis for {address}**

Based on demographic potential vs. current tenant mix:

**High Priority Opportunities** (strong demand, no current presence):
1. **Fast Casual Mediterranean** - 89% match score
   - High income, health-conscious demo underserved
   - Competitors: None within 3 miles
   - Suggested: Cava, Naf Naf Grill

2. **Boutique Fitness** - 85% match score
   - Young professional density supports premium fitness
   - Competitors: 1 traditional gym (5 miles)
   - Suggested: Orangetheory, F45, Barry's

3. **Urgent Care/Medical** - 82% match score
   - Healthcare employment cluster nearby
   - Family demographic needs convenient care
   - Suggested: CityMD, MinuteClinic expansion

**Medium Priority Opportunities**:
4. **Coffee/Café (Third Wave)** - 78% match score
5. **Pet Services (Grooming/Daycare)** - 75% match score
6. **Kids Entertainment** - 72% match score

**Categories Well-Served**:
- Quick Service Restaurants
- Wireless/Electronics
- Beauty/Personal Care

*Recommendation*: Prioritize Fast Casual Mediterranean and Boutique Fitness for 5,500 sq ft endcap and 3,800 sq ft inline spaces.""",
}


def run_agent(agent_name: str, address: str) -> str:
    """
    Run an agent and return results.

    Demographics agent uses real Census ACS data.
    Tenant roster agent uses real Google Places data.
    Other agents still use simulated data (to be implemented).
    """
    import asyncio

    if agent_name == "demographics":
        from app.services.census import analyze_demographics
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(analyze_demographics(address))
            loop.close()
            return result
        except Exception as e:
            return f"Error fetching demographics data: {str(e)}"

    if agent_name == "tenant_roster":
        from app.services.places import analyze_tenant_roster
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(analyze_tenant_roster(address))
            loop.close()
            return result
        except Exception as e:
            return f"Error fetching tenant data: {str(e)}"

    if agent_name == "void_analysis":
        from app.agents.void_analysis import generate_void_report
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(generate_void_report(address))
            loop.close()
            return result
        except Exception as e:
            return f"Error generating void analysis: {str(e)}"

    # Other agents still use simulated data
    if agent_name in AGENT_SIMULATIONS:
        return AGENT_SIMULATIONS[agent_name](address)
    return f"Agent '{agent_name}' is not yet implemented."


async def run_agent_async(
    agent_name: str,
    address: str,
    user_id: str | None = None,
    credential=None,
    progress_callback=None,
    demographics_data: dict | None = None,
    tenants_data: list[dict] | None = None,
) -> str:
    """
    Async version of run_agent for use in async contexts.

    For browser-based agents, requires user_id and credential.
    """
    if agent_name == "demographics":
        # Check if we should use browser-based agent (SiteUSA)
        if credential and credential.site_name.lower() == "siteusa":
            from app.agents.siteusa_demographics import SiteUSADemographicsAgent

            agent = SiteUSADemographicsAgent(progress_callback=progress_callback)
            result = await agent.execute(
                "demographics",
                {
                    "address": address,
                    "user_id": user_id,
                    "credential": credential,
                },
            )
            return result.content

        # Fall back to Census API
        from app.services.census import analyze_demographics

        return await analyze_demographics(address)

    if agent_name == "visitor_traffic":
        # Visitor traffic comes from Placer.ai (mobile data - people visiting)
        if credential and credential.site_name.lower() == "placer":
            from app.agents.placer_ai import PlacerAIFootTrafficAgent

            agent = PlacerAIFootTrafficAgent(progress_callback=progress_callback)
            result = await agent.execute(
                "visitor_traffic",
                {
                    "address": address,
                    "user_id": user_id,
                    "credential": credential,
                },
            )
            return result.content

        # Stub data (for development when no credentials)
        if "visitor_traffic" in AGENT_SIMULATIONS:
            return AGENT_SIMULATIONS["visitor_traffic"](address)
        return "Visitor traffic data requires Placer.ai credentials."

    if agent_name == "vehicle_traffic":
        # Vehicle traffic (VPD) comes from SiteUSA
        if credential and credential.site_name.lower() == "siteusa":
            from app.agents.siteusa_demographics import SiteUSAVehicleTrafficAgent

            agent = SiteUSAVehicleTrafficAgent(progress_callback=progress_callback)
            result = await agent.execute(
                "vehicle_traffic",
                {
                    "address": address,
                    "user_id": user_id,
                    "credential": credential,
                },
            )
            return result.content

        # Stub data (for development when no credentials)
        if "vehicle_traffic" in AGENT_SIMULATIONS:
            return AGENT_SIMULATIONS["vehicle_traffic"](address)
        return "Vehicle traffic (VPD) data requires SiteUSA credentials."

    if agent_name == "tenant_roster":
        # Priority 1: CoStar (premium data with lease details)
        if credential and credential.site_name.lower() == "costar":
            from app.agents.costar import CoStarTenantAgent
            try:
                agent = CoStarTenantAgent(progress_callback=progress_callback)
                result = await agent.execute(
                    "tenant_roster",
                    {
                        "address": address,
                        "user_id": user_id,
                        "credential": credential,
                    },
                )
                return result.content
            except Exception as e:
                print(f"[ORCHESTRATOR] CoStar error, falling back to Google Places: {e}")

        # Priority 2: Google Places (free, basic data)
        from app.services.places import analyze_tenant_roster
        return await analyze_tenant_roster(address)

    if agent_name == "void_analysis":
        # Priority 1: Placer.ai browser agent (best void data with match scores)
        if credential and credential.site_name.lower() == "placer":
            from app.agents.placer_ai import PlacerAIVoidAnalysisAgent

            agent = PlacerAIVoidAnalysisAgent(progress_callback=progress_callback)
            result = await agent.execute(
                "void_analysis",
                {
                    "address": address,
                    "user_id": user_id,
                    "credential": credential,
                },
            )
            return result.content

        # Priority 2: Claude-based void analysis (uses demographics + tenant data)
        from app.agents.void_analysis import generate_void_report

        return await generate_void_report(
            property_address=address,
            existing_tenants=tenants_data,
            demographics=demographics_data,
        )

    if agent_name == "customer_profile":
        # Priority 1: Placer.ai browser agent (actual visitors via mobile data)
        if credential and credential.site_name.lower() == "placer":
            from app.agents.placer_ai import PlacerAICustomerProfileAgent

            agent = PlacerAICustomerProfileAgent(progress_callback=progress_callback)
            result = await agent.execute(
                "customer_profile",
                {
                    "address": address,
                    "user_id": user_id,
                    "credential": credential,
                },
            )
            return result.content

        # Priority 2: Stub data (for development when no credentials)
        from app.services.placer import analyze_customer_profile
        return await analyze_customer_profile(address)

    if agent_name == "outreach":
        # Outreach agent for email campaigns
        from app.agents.outreach import OutreachAgent

        agent = OutreachAgent()
        # Extract void results and user info from context if available
        void_results = demographics_data.get("void_results", []) if demographics_data else []
        result = await agent.execute(
            "outreach",
            {
                "action": "create_campaign",
                "void_results": void_results,
                "property_address": address,
                "property_name": address,  # Will be refined from context
                "user_id": user_id,
                "from_name": "",  # Will be filled from user profile
                "from_email": "",  # Will be filled from user profile
            },
        )
        return result.content

    # Other agents still use simulated data
    if agent_name in AGENT_SIMULATIONS:
        return AGENT_SIMULATIONS[agent_name](address)
    return f"Agent '{agent_name}' is not yet implemented."


def is_browser_based_agent(agent_name: str, credential=None) -> bool:
    """
    Check if an agent requires browser automation.

    Args:
        agent_name: Name of the agent
        credential: Optional credential to check which data source is being used

    Returns:
        True if browser automation is required
    """
    # Explicitly browser-based agents
    browser_agents = {
        "siteusa_demographics",
        "siteusa_vehicle_traffic",
        "placer_visitor_traffic",
        "placer_customer_profile",
        "placer_void_analysis",
    }

    if agent_name.lower() in browser_agents:
        return True

    # Check if the credential indicates browser-based data source
    if credential:
        site = credential.site_name.lower()
        if site in ("placer", "siteusa", "costar"):
            return True

    return False


def get_agent_typical_duration(agent_name: str, credential=None) -> int:
    """
    Get the typical duration in seconds for an agent.

    Args:
        agent_name: Name of the agent
        credential: Optional credential to determine if browser-based

    Returns:
        Expected duration in seconds
    """
    # Base durations for API-based agents
    api_durations = {
        "demographics": 5,  # Census API is fast
        "tenant_roster": 3,  # Google Places is fast
        "void_analysis": 8,  # Claude analysis
        "visitor_traffic": 2,  # Stub data (Placer.ai)
        "vehicle_traffic": 2,  # Stub data (SiteUSA VPD)
        "customer_profile": 2,  # Stub data
        "trade_data": 2,  # Simulated for now
    }

    # Browser-based agent durations (slower due to scraping)
    browser_durations = {
        "siteusa_demographics": 45,
        "siteusa_vehicle_traffic": 50,  # SiteUSA VPD data
        "placer_visitor_traffic": 45,  # Placer.ai foot traffic
        "placer_customer_profile": 45,
        "placer_void_analysis": 50,
        "costar_tenant_roster": 60,
        "costar_property_info": 45,
    }

    # Check explicit browser agent names first
    if agent_name.lower() in browser_durations:
        return browser_durations[agent_name.lower()]

    # If credential indicates browser-based source, use longer duration
    if credential:
        site = credential.site_name.lower()
        if site == "placer":
            placer_mapping = {
                "visitor_traffic": 45,
                "customer_profile": 45,
                "void_analysis": 50,
            }
            return placer_mapping.get(agent_name.lower(), 45)
        elif site == "siteusa":
            siteusa_mapping = {
                "demographics": 45,
                "vehicle_traffic": 50,
            }
            return siteusa_mapping.get(agent_name.lower(), 45)
        elif site == "costar":
            costar_mapping = {
                "tenant_roster": 60,
                "property_info": 45,
            }
            return costar_mapping.get(agent_name.lower(), 50)

    return api_durations.get(agent_name.lower(), 5)


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
