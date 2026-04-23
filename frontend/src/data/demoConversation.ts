import type { WorkflowStep, AgentType } from '../types/chat';

/**
 * Interactive demo walkthrough for investor presentations.
 * Each step is triggered by pressing Enter, with realistic delays for agent work.
 */

export const DEMO_PROPERTY = {
  name: "Riverside Plaza Shopping Center",
  address: "2500 Riverside Drive, Stamford, CT 06902",
};

// Step types for the walkthrough
export type DemoStepType =
  | 'user_message'      // User sends a message
  | 'orchestrator'      // Orchestrator responds
  | 'workflow_init'     // Initialize workflow with agents
  | 'agents_start'      // All agents start working simultaneously
  | 'agent_working'     // Agent starts working (with delay)
  | 'agent_result'      // Agent returns result
  | 'synthesis'         // Orchestrator synthesizes results
  | 'user_followup'     // User asks follow-up
  | 'notification';     // Notification agent results

export interface DemoStep {
  type: DemoStepType;
  agentType?: AgentType;
  content?: string;
  workflowSteps?: Partial<WorkflowStep>[];
  delayMs?: number;  // Delay before this step completes
  autoAdvance?: boolean; // Auto-advance to next step after delay
}

// The complete demo walkthrough
export const DEMO_STEPS: DemoStep[] = [
  // Step 1: User asks for analysis
  {
    type: 'user_message',
    content: `I'd like a comprehensive analysis of ${DEMO_PROPERTY.address}. Can you run a full property assessment including demographics, current tenants, foot traffic, and identify any void opportunities?`,
  },

  // Step 2: Orchestrator acknowledges and plans
  {
    type: 'orchestrator',
    content: `I'll run a comprehensive analysis of **Riverside Plaza Shopping Center** in Stamford, CT. Let me coordinate our specialized agents to gather the data you need.

I'm initiating the following analyses:
- **Demographics Agent** - Trade area population and income data
- **Tenant Roster Agent** - Current tenant mix from Google Places
- **Foot Traffic Agent** - Visitor patterns and performance metrics
- **Tenant Gap Analysis** - Gap identification and opportunities
- **Tenant Match Agent** - Match your clients to opportunities

This will take a moment as I gather data from multiple sources...`,
    delayMs: 1500,
    autoAdvance: true,
  },

  // Step 3: Initialize workflow
  {
    type: 'workflow_init',
    workflowSteps: [
      { agentType: 'demographics', description: 'Analyzing trade area demographics', status: 'pending' },
      { agentType: 'tenant-roster', description: 'Gathering current tenant roster', status: 'pending' },
      { agentType: 'foot-traffic', description: 'Analyzing foot traffic patterns', status: 'pending' },
      { agentType: 'void-analysis', description: 'Identifying void opportunities', status: 'pending' },
      { agentType: 'tenant-match', description: 'Matching client tenants to opportunities', status: 'pending' },
    ],
    delayMs: 500,
    autoAdvance: true,
  },

  // Step 4: All agents start working simultaneously
  {
    type: 'agents_start',
    delayMs: 2500,
    autoAdvance: true,
  },

  // Step 5: Demographics result
  {
    type: 'agent_result',
    agentType: 'demographics',
    content: `**Trade Area Demographics (5-mile radius)**

**Population & Households**
- **Total Population**: 287,543 residents
- **Total Households**: 108,234
- **Median Household Income**: $98,450
- **Households earning $100k+**: 48.3%

**Age Distribution**
- Under 18: 21.4% | 18-34: 24.8% | 35-54: 29.2% | 55+: 24.6%

**Education & Employment**
- Bachelor's degree or higher: **58.2%**
- Unemployment Rate: 3.2%

*Key Insight*: Affluent, highly-educated trade area with strong household incomes. Supports premium retail and upscale dining.

*Source: U.S. Census Bureau ACS 5-Year Estimates*`,
    delayMs: 800,
    autoAdvance: true,
  },

  // Step 6: Tenant roster result
  {
    type: 'agent_result',
    agentType: 'tenant-roster',
    content: `**Current Tenant Roster**
*Found 47 businesses within the shopping center*

**Anchors (3)**
- Whole Foods Market (42,000 sq ft)
- Nordstrom Rack (32,000 sq ft)
- REI (24,000 sq ft)

**Dining (19)**
- Full Service: The Capital Grille, Bartaco, Barcelona Wine Bar, True Food Kitchen
- Fast Casual: Chipotle, Shake Shack, sweetgreen, Chopt, Starbucks (x2)

**Retail (18)**
- Lululemon, Athleta, J.Crew, Sephora, Warby Parker, Bonobos

**Vacant Spaces (3)**
- 8,500 sq ft (former Williams Sonoma) - Endcap
- 4,200 sq ft (former Sur La Table) - Inline
- 2,800 sq ft (former Paper Source) - Inline

**Occupancy Rate**: 93.6%

*Sources: Google Places API, Yellow Pages Directory, Property Records*`,
    delayMs: 800,
    autoAdvance: true,
  },

  // Step 7: Foot traffic result
  {
    type: 'agent_result',
    agentType: 'foot-traffic',
    content: `**Foot Traffic Analysis**

**Monthly Metrics**
- **Total Monthly Visits**: 412,000
- **Unique Visitors**: 156,000
- **Visits per Visitor**: 2.64 (strong repeat rate)
- **YoY Growth**: +12.4%

**Peak Times**
- Busiest Days: Saturday (21,400), Sunday (18,300)
- Peak Hours: 12-2 PM, 5-7 PM
- Average Dwell Time: 68 minutes

**Visitor Profile**
- Female: 58% | Male: 42%
- Median HH Income: $112,000
- Within 5 miles: 62%

**Top Traffic Drivers**
1. Whole Foods (32%)
2. Dining cluster (28%)
3. Nordstrom Rack (18%)

*Source: Placer.ai Analytics*`,
    delayMs: 800,
    autoAdvance: true,
  },

  // Step 8: Void analysis result
  {
    type: 'agent_result',
    agentType: 'void-analysis',
    content: `**Tenant Gap Analysis - Top Opportunities**

**HIGH PRIORITY** (Strong demand, no current presence)

**1. Home/Kitchen Lifestyle - 92% Match**
- Gap: Williams Sonoma/Sur La Table spaces vacant
- Recommendations: Crate & Barrel, West Elm
- Estimated Sales PSF: $450-550

**2. Specialty Grocery/Gourmet - 89% Match**
- Gap: No artisan food/wine concept
- Recommendations: Murray's Cheese, Eataly corner
- Estimated Sales PSF: $600-800

**3. Athleisure/Active - 87% Match**
- Current: Lululemon, Athleta only
- Recommendations: Allbirds, Tracksmith, Peloton
- Estimated Sales PSF: $500-650

**MEDIUM PRIORITY**
4. Experiential Entertainment - 84%
5. Children's Enrichment - 81%
6. Pet Premium - 78%

**Recommended Leasing Strategy**
| Space | Target Tenant | Rent PSF |
|-------|---------------|----------|
| 8,500 sq ft endcap | Crate & Barrel | $65-75 |
| 4,200 sq ft inline | Murray's Cheese | $70-85 |
| 2,800 sq ft inline | Allbirds | $75-90 |

*Projected Impact: +$1.2M annual rent, +8-12% traffic lift*`,
    delayMs: 1000,
    autoAdvance: true,
  },

  // Step 9: Tenant match result
  {
    type: 'agent_result',
    agentType: 'tenant-match',
    content: `**Client Tenant Matches**
*Searched 47 active tenant clients against void opportunities*

---

**HOME/KITCHEN LIFESTYLE** (8,500 sq ft endcap)

| Tenant | Match | Criteria Fit |
|--------|-------|--------------|
| **West Elm** | 94% | Seeking 8-12k sq ft • Affluent suburbs • Near Whole Foods ✓ |
| **Crate & Barrel** | 91% | Expanding in CT • Needs $90k+ HH income ✓ • Endcap preferred ✓ |
| **Pottery Barn** | 88% | 7-10k sq ft target • Family demographics ✓ |

---

**SPECIALTY FOOD/GOURMET** (4,200 sq ft inline)

| Tenant | Match | Criteria Fit |
|--------|-------|--------------|
| **Murray's Cheese** | 92% | CT/NY expansion • Requires grocery anchor (Whole Foods) ✓ |
| **Eataly Corner** | 87% | Seeking affluent trade areas • 4-6k sq ft ✓ |
| **Di Bruno Bros** | 84% | Northeast focus • High foot traffic required ✓ |

---

**ATHLEISURE/ACTIVE** (2,800 sq ft inline)

| Tenant | Match | Criteria Fit |
|--------|-------|--------------|
| **Allbirds** | 96% | 2.5-3.5k sq ft exact match ✓ • Educated demo ✓ • Near Lululemon ✓ |
| **Vuori** | 91% | Premium centers • $100k+ visitor income ✓ |
| **Tracksmith** | 89% | Suburban expansion • Running community presence |

---

**Top 3 Recommendations**
1. **Allbirds** → 2,800 sq ft inline (96% match)
2. **West Elm** → 8,500 sq ft endcap (94% match)
3. **Murray's Cheese** → 4,200 sq ft inline (92% match)

*Matching based on tenant space requirements, demographic preferences, co-tenancy needs, and expansion criteria from your CRM.*`,
    delayMs: 1000,
    autoAdvance: true,
  },

  // Step 14: Orchestrator synthesis
  {
    type: 'synthesis',
    content: `## Executive Summary: Riverside Plaza Shopping Center

I've completed the comprehensive analysis. Here are the key findings:

### Property Health: **Strong**
- 93.6% occupancy with 3 strategic vacancies
- +12.4% YoY traffic growth
- 68-min average dwell time (excellent engagement)

### Trade Area Strengths
- Affluent demographics ($98k median HH income)
- Highly educated (58% bachelor's+)
- Strong employment base

### Void Opportunities → Matched Tenants
| Void Category | Best Match | Score | Available Space |
|--------------|------------|-------|-----------------|
| Home/Kitchen | **West Elm** | 94% | 8,500 sq ft endcap |
| Specialty Food | **Murray's Cheese** | 92% | 4,200 sq ft inline |
| Athleisure | **Allbirds** | 96% | 2,800 sq ft inline |

### Potential Impact
- Fill all 3 vacancies: **+$1.2M annual rent**
- Expected traffic lift: **+8-12%**

---

Would you like me to **notify these matched tenants** about the opportunity?`,
    delayMs: 1200,
  },

  // Step 15: User follow-up about notifications
  {
    type: 'user_followup',
    content: `Yes, please reach out to Allbirds, West Elm, and Murray's Cheese about these opportunities.`,
  },

  // Step 16: Orchestrator initiates notification
  {
    type: 'orchestrator',
    content: `I'll prepare personalized outreach for each tenant based on their specific criteria and the property fit. Let me coordinate with the Notification Agent...`,
    delayMs: 800,
    autoAdvance: true,
  },

  // Step 17: Notification agent working
  {
    type: 'agent_working',
    agentType: 'notification',
    delayMs: 2000,
    autoAdvance: true,
  },

  // Step 18: Notification result
  {
    type: 'notification',
    agentType: 'notification',
    content: `**Tenant Outreach Summary**

**PERSONALIZED EMAILS SENT**

| Tenant | Contact | Role | Status |
|--------|---------|------|--------|
| **Allbirds** | Jessica Park | Dir. of Real Estate | ✅ Sent |
| **West Elm** | Marcus Thompson | VP Expansion | ✅ Sent |
| **Murray's Cheese** | Rachel Goldman | Site Selection | ✅ Sent |

---

**Email Personalization**

**Allbirds** - Subject: "2,800 SF Opportunity in Stamford - Matches Your Expansion Criteria"
> Highlighted: Exact size match, educated demographics (58% bachelor's+), proximity to Lululemon & Athleta, 412k monthly visits

**West Elm** - Subject: "Premium Endcap Available - Affluent Stamford Trade Area"
> Highlighted: 8,500 SF endcap, Whole Foods anchor, $98k median HH income, former Williams Sonoma space

**Murray's Cheese** - Subject: "CT Expansion Opportunity - Whole Foods Anchored Center"
> Highlighted: Grocery anchor requirement met, 4,200 SF inline, affluent foodie demographics

---

**Follow-up Schedule**
| Tenant | Next Action | When |
|--------|-------------|------|
| Allbirds | Phone call | 3 days |
| West Elm | Email follow-up | 5 days |
| Murray's Cheese | Phone call | 3 days |

**LinkedIn Outreach** (Pending your approval)
- Connection request to Jessica Park (Allbirds)
- InMail to Marcus Thompson (West Elm)`,
    delayMs: 800,
  },

  // Step 19: Final orchestrator message
  {
    type: 'orchestrator',
    content: `All tenant outreach has been sent successfully.

**Actions Completed:**
- ✅ Analyzed 287k population trade area
- ✅ Identified 3 void opportunities from 47-tenant roster
- ✅ Matched 9 client tenants to opportunities
- ✅ Sent personalized emails to top 3 matches
- ✅ Scheduled follow-up reminders

Each email was personalized with the specific data points that match each tenant's expansion criteria - space size, demographics, co-tenancy requirements, and traffic metrics.

---

**Demo Complete!**

This walkthrough demonstrated Space Goose's full pipeline:
1. **Data Aggregation** - Demographics, tenants, foot traffic
2. **Tenant Gap Analysis** - Identified category gaps
3. **Tenant Matching** - Matched your clients to opportunities
4. **Automated Outreach** - Personalized emails with relevant data

*Press Enter to restart the demo or click "Exit Demo" to explore the platform.*`,
  },
];

// Helper to generate IDs for demo messages
export const generateDemoId = (prefix: string, index: number) => `demo-${prefix}-${index}`;
