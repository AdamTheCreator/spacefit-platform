export type AgentType =
  | 'orchestrator'
  | 'demographics'
  | 'tenant-roster'
  | 'foot-traffic'
  | 'void-analysis'
  | 'tenant-match'
  | 'notification'
  | 'placer'
  | 'siteusa'
  | 'costar'
  | 'outreach'
  | 'scout'
  | 'analyst'
  | 'matchmaker';

export type MessageRole = 'user' | 'agent' | 'system';

export interface MessageReceipt {
  agents: string[];
  seconds: number;
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  agentType?: AgentType;
  timestamp: Date;
  isStreaming?: boolean;
  pending?: boolean;
  receipt?: MessageReceipt;
}

/**
 * A recruitable tenant a void/matchmaker analysis surfaced, emitted by the
 * backend `tenant_candidates` WS event so the chat can offer "save as Contacts".
 * Mirrors the backend `TenantPromotionItem`.
 */
export interface TenantCandidate {
  name: string;
  sector?: string | null;
  category?: string | null;
  estimated_sf?: number | null;
  priority?: string | null;
  match_score?: number | null;
  rationale?: string | null;
  source_address?: string | null;
}

export type WorkflowStepStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'error'
  | 'timed_out'
  | 'circuit_open';

export interface WorkflowStep {
  id: string;
  agentType: AgentType;
  status: WorkflowStepStatus;
  description: string;
  errorMessage?: string;
  errorKind?: string;
  elapsedMs?: number;
}

export interface AgentInfo {
  type: AgentType;
  name: string;
  description: string;
  color: string;
}

export const AGENTS: Record<AgentType, AgentInfo> = {
  orchestrator: {
    type: 'orchestrator',
    name: 'Space Goose Assistant',
    description: 'Main orchestrator that coordinates all agents',
    color: 'bg-blue-500',
  },
  demographics: {
    type: 'demographics',
    name: 'Demographics Agent',
    description: 'Analyzes ACS and trade area data',
    color: 'bg-purple-500',
  },
  'tenant-roster': {
    type: 'tenant-roster',
    name: 'Tenant Roster Agent',
    description: 'Retrieves tenant information from platforms',
    color: 'bg-green-500',
  },
  'void-analysis': {
    type: 'void-analysis',
    name: 'Tenant Gap Analysis',
    description: 'Identifies gaps and opportunities',
    color: 'bg-red-500',
  },
  'tenant-match': {
    type: 'tenant-match',
    name: 'Tenant Match Agent',
    description: 'Matches client tenants to property opportunities',
    color: 'bg-cyan-500',
  },
  notification: {
    type: 'notification',
    name: 'Notification Agent',
    description: 'Manages client notifications and outreach',
    color: 'bg-teal-500',
  },
  placer: {
    type: 'placer',
    name: 'Placer.ai',
    description: 'Visitor traffic, customer profiles, and gap analysis',
    color: 'bg-emerald-500',
  },
  siteusa: {
    type: 'siteusa',
    name: 'SiteUSA',
    description: 'Vehicle traffic (VPD) and demographics data',
    color: 'bg-amber-500',
  },
  'foot-traffic': {
    type: 'foot-traffic',
    name: 'Foot Traffic Agent',
    description: 'Analyzes foot traffic patterns from Placer.ai',
    color: 'bg-orange-500',
  },
  costar: {
    type: 'costar',
    name: 'CoStar',
    description: 'Premium tenant and lease data',
    color: 'bg-indigo-500',
  },
  outreach: {
    type: 'outreach',
    name: 'Outreach',
    description: 'Drafts outreach emails to candidate tenants',
    color: 'bg-pink-500',
  },
  scout: {
    type: 'scout',
    name: 'Scout',
    description: 'Finds properties and nearby businesses',
    color: 'bg-sky-500',
  },
  analyst: {
    type: 'analyst',
    name: 'Analyst',
    description: 'Analyzes the trade area and tenant gaps',
    color: 'bg-violet-500',
  },
  matchmaker: {
    type: 'matchmaker',
    name: 'Matchmaker',
    description: 'Matches gaps to candidate tenants',
    color: 'bg-fuchsia-500',
  },
};
