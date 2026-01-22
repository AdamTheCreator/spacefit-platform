import type { AgentType, WorkflowStep } from '../../types/chat';

// Agent configuration
const AGENT_CONFIG: Record<string, { name: string; shortName: string; color: string; borderColor: string }> = {
  'demographics': { name: 'Demographics', shortName: 'Demo', color: 'bg-purple-500', borderColor: 'border-purple-500' },
  'tenant-roster': { name: 'Tenant Roster', shortName: 'Tenants', color: 'bg-green-500', borderColor: 'border-green-500' },
  'void-analysis': { name: 'Void Analysis', shortName: 'Voids', color: 'bg-red-500', borderColor: 'border-red-500' },
  'tenant-match': { name: 'Tenant Match', shortName: 'Match', color: 'bg-cyan-500', borderColor: 'border-cyan-500' },
  'notification': { name: 'Notifications', shortName: 'Notify', color: 'bg-teal-500', borderColor: 'border-teal-500' },
  'orchestrator': { name: 'Assistant', shortName: 'Main', color: 'bg-blue-500', borderColor: 'border-blue-500' },
  'placer': { name: 'Placer.ai', shortName: 'Placer', color: 'bg-emerald-500', borderColor: 'border-emerald-500' },
  'siteusa': { name: 'SiteUSA', shortName: 'SiteUSA', color: 'bg-amber-500', borderColor: 'border-amber-500' },
};

interface AgentStatusStripProps {
  workflowSteps: WorkflowStep[];
  activeAgentType: AgentType | null;
  isProcessing: boolean;
}

// Horizontal agent status strip (Warp-style) - sits above input
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
      <div className="border-t border-gray-800 bg-gray-900/95 backdrop-blur-sm">
        {/* Animated progress bar */}
        <div className="h-0.5 bg-gray-800 overflow-hidden">
          <div
            className="h-full w-full bg-gradient-to-r from-indigo-500 via-purple-500 to-indigo-500 bg-[length:200%_100%] animate-shimmer"
          />
        </div>

        {/* Processing indicator */}
        <div className="px-3 sm:px-6 py-2">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 bg-indigo-400 rounded-full animate-pulse" />
            <span className="text-xs text-gray-400">Thinking...</span>
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
    <div className="border-t border-gray-800 bg-gray-900/95 backdrop-blur-sm">
      {/* Progress bar - thin line at top */}
      <div className="h-0.5 bg-gray-800">
        <div
          className={`h-full transition-all duration-500 ${
            allComplete
              ? 'bg-green-500'
              : 'bg-gradient-to-r from-indigo-500 via-purple-500 to-indigo-500 bg-[length:200%_100%] animate-shimmer'
          }`}
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Agent chips */}
      <div className="px-3 sm:px-6 py-2">
        <div className="flex items-center gap-2 overflow-x-auto scrollbar-hide">
          {/* Status label */}
          <div className="flex-shrink-0 flex items-center gap-2 pr-3 border-r border-gray-700">
            {isProcessing && !allComplete ? (
              <span className="w-2 h-2 bg-indigo-400 rounded-full animate-pulse" />
            ) : allComplete ? (
              <svg className="w-4 h-4 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
            ) : (
              <span className="w-2 h-2 bg-gray-500 rounded-full" />
            )}
            <span className="text-xs text-gray-400 whitespace-nowrap">
              {allComplete ? 'Complete' : `${completedCount}/${totalCount}`}
            </span>
          </div>

          {/* Agent chips */}
          {workflowSteps.map((step) => {
            const config = AGENT_CONFIG[step.agentType] || {
              name: step.agentType,
              shortName: step.agentType.slice(0, 4),
              color: 'bg-gray-500',
              borderColor: 'border-gray-500',
            };
            const isActive = step.agentType === activeAgentType;
            const isCompleted = step.status === 'completed';
            const isRunning = step.status === 'running';

            return (
              <div
                key={step.id}
                className={`flex-shrink-0 flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-all duration-300 ${
                  isCompleted
                    ? 'bg-gray-800 text-gray-400 border border-gray-700'
                    : isRunning || isActive
                    ? `bg-gray-800 text-white border ${config.borderColor}`
                    : 'bg-gray-800/50 text-gray-500 border border-gray-700/50'
                }`}
              >
                {/* Status dot */}
                <span className="relative flex-shrink-0">
                  <span
                    className={`block w-2 h-2 rounded-full ${
                      isCompleted ? 'bg-green-400' : isRunning ? config.color : 'bg-gray-600'
                    } ${isRunning ? 'animate-pulse' : ''}`}
                  />
                  {isRunning && (
                    <span className={`absolute inset-0 rounded-full ${config.color} animate-ping opacity-50`} />
                  )}
                </span>

                {/* Agent name - use step description if available, otherwise config name */}
                <span className="sm:hidden">{step.description?.split(':')[0] || config.shortName}</span>
                <span className="hidden sm:inline">{step.description || config.name}</span>

                {/* Checkmark for completed */}
                {isCompleted && (
                  <svg className="w-3 h-3 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                )}

                {/* Spinner for running */}
                {isRunning && (
                  <span className="w-3 h-3 border border-white/30 border-t-white rounded-full animate-spin" />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
