import { useMemo } from 'react';
import { AGENTS, type AgentType, type WorkflowStep } from '../../types/chat';

interface AgentActivityPanelProps {
  isProcessing: boolean;
  activeAgentType: AgentType | null;
  workflowSteps: WorkflowStep[];
}

// Agent icons as simple SVG components
const AgentIcons: Record<AgentType, React.ReactNode> = {
  orchestrator: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v4M12 18v4M2 12h4M18 12h4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
    </svg>
  ),
  demographics: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  'tenant-roster': (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9,22 9,12 15,12 15,22" />
    </svg>
  ),
  'foot-traffic': (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
    </svg>
  ),
  'void-analysis': (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <circle cx="11" cy="11" r="8" />
      <path d="M21 21l-4.35-4.35" />
      <path d="M11 8v6M8 11h6" />
    </svg>
  ),
  notification: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  ),
  'tenant-match': (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  placer: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  ),
  siteusa: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
      <line x1="3" y1="9" x2="21" y2="9" />
      <line x1="9" y1="21" x2="9" y2="9" />
    </svg>
  ),
  costar: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  ),
  outreach: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
      <polyline points="22,6 12,13 2,6" />
    </svg>
  ),
};

// Color mappings for Tailwind classes
const colorMap: Record<AgentType, { bg: string; text: string; glow: string; shadow: string }> = {
  orchestrator: {
    bg: 'bg-blue-500',
    text: 'text-blue-400',
    glow: 'shadow-blue-500/50',
    shadow: 'shadow-[0_0_20px_rgba(59,130,246,0.5)]',
  },
  demographics: {
    bg: 'bg-purple-500',
    text: 'text-purple-400',
    glow: 'shadow-purple-500/50',
    shadow: 'shadow-[0_0_20px_rgba(168,85,247,0.5)]',
  },
  'tenant-roster': {
    bg: 'bg-green-500',
    text: 'text-green-400',
    glow: 'shadow-green-500/50',
    shadow: 'shadow-[0_0_20px_rgba(34,197,94,0.5)]',
  },
  'foot-traffic': {
    bg: 'bg-orange-500',
    text: 'text-orange-400',
    glow: 'shadow-orange-500/50',
    shadow: 'shadow-[0_0_20px_rgba(249,115,22,0.5)]',
  },
  'void-analysis': {
    bg: 'bg-red-500',
    text: 'text-red-400',
    glow: 'shadow-red-500/50',
    shadow: 'shadow-[0_0_20px_rgba(239,68,68,0.5)]',
  },
  notification: {
    bg: 'bg-teal-500',
    text: 'text-teal-400',
    glow: 'shadow-teal-500/50',
    shadow: 'shadow-[0_0_20px_rgba(20,184,166,0.5)]',
  },
  'tenant-match': {
    bg: 'bg-cyan-500',
    text: 'text-cyan-400',
    glow: 'shadow-cyan-500/50',
    shadow: 'shadow-[0_0_20px_rgba(6,182,212,0.5)]',
  },
  placer: {
    bg: 'bg-emerald-500',
    text: 'text-emerald-400',
    glow: 'shadow-emerald-500/50',
    shadow: 'shadow-[0_0_20px_rgba(16,185,129,0.5)]',
  },
  siteusa: {
    bg: 'bg-amber-500',
    text: 'text-amber-400',
    glow: 'shadow-amber-500/50',
    shadow: 'shadow-[0_0_20px_rgba(245,158,11,0.5)]',
  },
  costar: {
    bg: 'bg-indigo-500',
    text: 'text-indigo-400',
    glow: 'shadow-indigo-500/50',
    shadow: 'shadow-[0_0_20px_rgba(99,102,241,0.5)]',
  },
  outreach: {
    bg: 'bg-pink-500',
    text: 'text-pink-400',
    glow: 'shadow-pink-500/50',
    shadow: 'shadow-[0_0_20px_rgba(236,72,153,0.5)]',
  },
};

export function AgentActivityPanel({
  isProcessing,
  activeAgentType,
  workflowSteps,
}: AgentActivityPanelProps) {
  // Determine agent states based on workflow steps
  const agentStates = useMemo(() => {
    const states: Record<AgentType, 'idle' | 'running' | 'completed' | 'pending'> = {
      orchestrator: 'idle',
      demographics: 'idle',
      'tenant-roster': 'idle',
      'foot-traffic': 'idle',
      'void-analysis': 'idle',
      'tenant-match': 'idle',
      notification: 'idle',
      placer: 'idle',
      siteusa: 'idle',
      costar: 'idle',
      outreach: 'idle',
    };

    // If processing but no workflow steps, orchestrator is thinking
    if (isProcessing && workflowSteps.length === 0) {
      states.orchestrator = 'running';
    }

    // Set states based on workflow steps
    workflowSteps.forEach((step) => {
      if (step.agentType in states) {
        states[step.agentType] = step.status === 'error' ? 'idle' : step.status;
      }
    });

    // Override with active agent if specified
    if (activeAgentType && activeAgentType in states) {
      states[activeAgentType] = 'running';
    }

    return states;
  }, [isProcessing, activeAgentType, workflowSteps]);

  // Check if any agent is active
  const hasActivity = isProcessing || Object.values(agentStates).some((s) => s === 'running');

  if (!hasActivity) {
    return null;
  }

  const agentOrder: AgentType[] = [
    'orchestrator',
    'demographics',
    'tenant-roster',
    'foot-traffic',
    'void-analysis',
    'tenant-match',
    'notification',
  ];

  return (
    <div className="bg-gray-800/60 backdrop-blur-sm border border-gray-700/50 rounded-2xl p-4 mb-4 overflow-hidden">
      {/* Header with animated bar */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative">
          <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
          <div className="absolute inset-0 w-2 h-2 rounded-full bg-blue-500 animate-ping" />
        </div>
        <span className="text-sm font-medium text-gray-300">Agent Activity</span>
        {isProcessing && (
          <div className="flex-1 h-1 bg-gray-700 rounded-full overflow-hidden ml-2">
            <div className="h-full bg-gradient-to-r from-blue-500 via-purple-500 to-blue-500 processing-bar"
                 style={{ width: '100%', backgroundSize: '200% 100%', animation: 'data-flow 2s linear infinite' }} />
          </div>
        )}
      </div>

      {/* Agent Grid */}
      <div className="grid grid-cols-3 gap-3">
        {agentOrder.map((agentType) => {
          const agent = AGENTS[agentType];
          const state = agentStates[agentType];
          const colors = colorMap[agentType];
          const isActive = state === 'running';
          const isCompleted = state === 'completed';
          const isPending = state === 'pending';

          return (
            <div
              key={agentType}
              className={`
                relative flex flex-col items-center p-3 rounded-xl transition-all duration-500
                ${isActive ? 'bg-gray-700/80 scale-105' : 'bg-gray-800/40'}
                ${isCompleted ? 'bg-green-900/20' : ''}
                ${isPending ? 'bg-gray-700/30' : ''}
              `}
            >
              {/* Agent Indicator Light */}
              <div className="relative mb-2">
                {/* Outer glow ring for active state */}
                {isActive && (
                  <>
                    <div
                      className={`absolute inset-0 rounded-full ${colors.bg} opacity-30 animate-ping`}
                      style={{ transform: 'scale(1.5)' }}
                    />
                    <div
                      className={`absolute inset-0 rounded-full ${colors.bg} opacity-20`}
                      style={{
                        transform: 'scale(2)',
                        animation: 'ripple 1.5s ease-out infinite',
                      }}
                    />
                  </>
                )}

                {/* Main indicator */}
                <div
                  className={`
                    relative w-10 h-10 rounded-full flex items-center justify-center
                    transition-all duration-500 ease-out
                    ${isActive ? `${colors.bg} ${colors.shadow}` : 'bg-gray-700'}
                    ${isActive ? 'animate-pulse' : ''}
                    ${isCompleted ? 'bg-green-600' : ''}
                    ${!isActive && !isCompleted ? 'opacity-50' : ''}
                  `}
                >
                  {/* Icon */}
                  <div className={`${isActive ? 'text-white' : colors.text} transition-colors duration-300`}>
                    {isCompleted ? (
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="w-5 h-5 text-white">
                        <path d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      AgentIcons[agentType]
                    )}
                  </div>

                  {/* Orbiting dot for running state */}
                  {isActive && (
                    <div
                      className="absolute w-2 h-2 bg-white rounded-full"
                      style={{
                        animation: 'orbit 1.2s linear infinite',
                      }}
                    />
                  )}
                </div>
              </div>

              {/* Agent Name */}
              <span
                className={`
                  text-xs font-medium text-center leading-tight transition-colors duration-300
                  ${isActive ? 'text-white' : 'text-gray-500'}
                  ${isCompleted ? 'text-green-400' : ''}
                `}
              >
                {agent.name.replace(' Agent', '')}
              </span>

              {/* Status indicator */}
              {isActive && (
                <span className="text-[10px] text-gray-400 mt-1 animate-pulse">Working...</span>
              )}
              {isCompleted && (
                <span className="text-[10px] text-green-500 mt-1">Done</span>
              )}
              {isPending && (
                <span className="text-[10px] text-gray-500 mt-1">Pending</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
