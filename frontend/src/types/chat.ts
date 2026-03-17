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
  | 'outreach';

export type MessageRole = 'user' | 'agent' | 'system';

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  agentType?: AgentType;
  timestamp: Date;
  isStreaming?: boolean;
  pending?: boolean;
}

export interface WorkflowStep {
  id: string;
  agentType: AgentType;
  status: 'pending' | 'running' | 'completed' | 'error';
  description: string;
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
    name: 'SpaceFit Assistant',
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
    name: 'Outreach Agent',
    description: 'Email campaign management',
    color: 'bg-pink-500',
  },
};
