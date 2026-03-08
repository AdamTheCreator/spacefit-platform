import type { AgentType, WorkflowStep } from '../../types/chat';

// Agent configuration with softer colors
const AGENT_CONFIG: Record<string, { name: string; shortName: string; color: string; bgColor: string }> = {
  'demographics': { name: 'Demographics', shortName: 'Demo', color: 'bg-[var(--accent)]', bgColor: 'bg-[var(--accent-subtle)]' },
  'tenant-roster': { name: 'Tenant Roster', shortName: 'Tenants', color: 'bg-[var(--color-success)]', bgColor: 'bg-[var(--bg-success)]' },
  'void-analysis': { name: 'Void Analysis', shortName: 'Voids', color: 'bg-[var(--color-error)]', bgColor: 'bg-[var(--bg-error)]' },
  'tenant-match': { name: 'Tenant Match', shortName: 'Match', color: 'bg-cyan-500', bgColor: 'bg-cyan-50' },
  'notification': { name: 'Notifications', shortName: 'Notify', color: 'bg-teal-500', bgColor: 'bg-teal-50' },
  'orchestrator': { name: 'Assistant', shortName: 'Main', color: 'bg-[var(--accent)]', bgColor: 'bg-[var(--accent-subtle)]' },
  'placer': { name: 'Placer.ai', shortName: 'Placer', color: 'bg-[var(--color-success)]', bgColor: 'bg-[var(--bg-success)]' },
  'siteusa': { name: 'SiteUSA', shortName: 'SiteUSA', color: 'bg-[var(--color-warning)]', bgColor: 'bg-[var(--bg-warning)]' },
};

interface AgentStatusStripProps {
  workflowSteps: WorkflowStep[];
  activeAgentType: AgentType | null;
  isProcessing: boolean;
}

// Horizontal agent status strip - sits above input
export function AgentStatusStrip({
  workflowSteps,
  activeAgentType,
  isProcessing,
}: AgentStatusStripProps) {
  // Don't show if no workflow steps and not processing
  if (workflowSteps.length === 0 && !isProcessing) return null;

  // Show simple processing indicator if processing but no workflow steps yet
  if (workflowSteps.length === 0 && isProcessing) {
    return (
      <div className="chat-input-shell border-t border-[var(--border-subtle)] bg-[var(--bg-secondary)]">
        {/* Animated progress bar */}
        <div className="chat-stage h-1 bg-[var(--bg-tertiary)] overflow-hidden rounded-full mt-3">
          <div className="h-full bg-[var(--accent)] rounded-full animate-pulse" style={{width: '40%'}} />
        </div>

        {/* Processing indicator */}
        <div className="chat-stage px-1 py-2.5">
          <div className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[var(--accent)] animate-pulse-soft" />
            <span className="text-sm text-industrial-secondary">Thinking...</span>
          </div>
        </div>
      </div>
    );
  }

  const completedCount = workflowSteps.filter(s => s.status === 'completed').length;
  const totalCount = workflowSteps.length;
  const progressPercent = (completedCount / totalCount) * 100;
  const allComplete = completedCount === totalCount;

  return (
    <div className="chat-input-shell border-t border-[var(--border-subtle)] bg-[var(--bg-secondary)]">
      {/* Progress bar - rounded at top */}
      <div className="chat-stage h-1 bg-[var(--bg-tertiary)] mt-3 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out ${
            allComplete
              ? 'bg-[var(--color-success)]'
              : 'bg-[var(--accent)]'
          }`}
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Agent chips */}
      <div className="chat-stage px-1 py-2.5">
        <div className="flex items-center gap-2 overflow-x-auto scrollbar-hide">
          {/* Status label */}
          <div className="flex-shrink-0 flex items-center gap-2 pr-3 border-r border-[var(--border-subtle)]">
            {isProcessing && !allComplete ? (
              <span className="w-2.5 h-2.5 rounded-full bg-[var(--accent)] animate-pulse-soft" />
            ) : allComplete ? (
              <svg className="w-4 h-4 text-[var(--color-success)]" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
            ) : (
              <span className="w-2.5 h-2.5 rounded-full bg-[var(--text-muted)]" />
            )}
            <span className="text-xs font-medium text-industrial-muted whitespace-nowrap">
              {allComplete ? 'Complete' : `${completedCount} of ${totalCount}`}
            </span>
          </div>

          {/* Agent chips - softer pill style */}
          {workflowSteps.map((step) => {
            const config = AGENT_CONFIG[step.agentType] || {
              name: step.agentType,
              shortName: step.agentType.slice(0, 4),
              color: 'bg-[var(--text-muted)]',
              bgColor: 'bg-[var(--bg-tertiary)]',
            };
            const isActive = step.agentType === activeAgentType;
            const isCompleted = step.status === 'completed';
            const isRunning = step.status === 'running';

            return (
              <div
                key={step.id}
                className={`flex-shrink-0 flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200 ${
                  isCompleted
                    ? 'bg-[var(--bg-success)] text-[var(--color-success)]'
                    : isRunning || isActive
                    ? `${config.bgColor} text-industrial`
                    : 'bg-[var(--bg-tertiary)] text-industrial-muted'
                }`}
              >
                {/* Status dot */}
                <span className="relative flex-shrink-0">
                  <span
                    className={`block w-2 h-2 rounded-full ${
                      isCompleted ? 'bg-[var(--color-success)]' : isRunning ? config.color : 'bg-[var(--text-muted)]'
                    } ${isRunning ? 'animate-pulse-soft' : ''}`}
                  />
                  {isRunning && (
                    <span className={`absolute inset-0 rounded-full ${config.color} animate-ping opacity-40`} />
                  )}
                </span>

                {/* Agent name */}
                <span className="sm:hidden">{step.description?.split(':')[0] || config.shortName}</span>
                <span className="hidden sm:inline">{step.description || config.name}</span>

                {/* Checkmark for completed */}
                {isCompleted && (
                  <svg className="w-3.5 h-3.5 text-[var(--color-success)]" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                )}

                {/* 3-dot bounce indicator for running */}
                {isRunning && (
                  <span className="flex gap-0.5 items-center">
                    <span className="w-1 h-1 rounded-full bg-current animate-bounce [animation-delay:-0.3s]" />
                    <span className="w-1 h-1 rounded-full bg-current animate-bounce [animation-delay:-0.15s]" />
                    <span className="w-1 h-1 rounded-full bg-current animate-bounce" />
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
