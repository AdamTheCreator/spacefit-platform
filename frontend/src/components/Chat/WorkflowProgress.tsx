import type { WorkflowStep } from '../../types/chat';
import { AGENTS } from '../../types/chat';

interface WorkflowProgressProps {
  steps: WorkflowStep[];
}

// Map agent types to gradient colors for the glow effect
const glowColors: Record<string, string> = {
  orchestrator: 'rgba(59, 130, 246, 0.5)',
  demographics: 'rgba(168, 85, 247, 0.5)',
  'tenant-roster': 'rgba(34, 197, 94, 0.5)',
  'void-analysis': 'rgba(239, 68, 68, 0.5)',
  notification: 'rgba(20, 184, 166, 0.5)',
  placer: 'rgba(16, 185, 129, 0.5)',
  siteusa: 'rgba(245, 158, 11, 0.5)',
};

export function WorkflowProgress({ steps }: WorkflowProgressProps) {
  if (steps.length === 0) return null;

  const runningSteps = steps.filter((s) => s.status === 'running');
  const completedSteps = steps.filter((s) => s.status === 'completed');
  const progress = steps.length > 0 ? (completedSteps.length / steps.length) * 100 : 0;

  return (
    <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl p-4 mb-4 overflow-hidden">
      {/* Header with progress bar */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-gray-400">
          Workflow Progress
        </h3>
        <span className="text-xs text-gray-500">
          {completedSteps.length}/{steps.length} complete
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 bg-gray-700 rounded-full mb-4 overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-blue-500 via-purple-500 to-green-500 rounded-full transition-all duration-500 ease-out relative"
          style={{ width: `${progress}%` }}
        >
          {runningSteps.length > 0 && (
            <div className="absolute inset-0 bg-white/20 animate-pulse" />
          )}
        </div>
      </div>

      {/* Steps */}
      <div className="space-y-2">
        {steps.map((step) => {
          const agent = AGENTS[step.agentType];
          const isRunning = step.status === 'running';
          const isCompleted = step.status === 'completed';
          const glowColor = glowColors[step.agentType] || 'rgba(59, 130, 246, 0.5)';

          return (
            <div
              key={step.id}
              className={`
                flex items-center gap-3 p-2 rounded-lg transition-all duration-300
                ${isRunning ? 'bg-gray-700/50' : ''}
                ${isCompleted ? 'opacity-60' : ''}
              `}
              style={isRunning ? { boxShadow: `0 0 20px ${glowColor}` } : {}}
            >
              {/* Status indicator */}
              <div className="flex items-center justify-center w-6 h-6 relative">
                {isCompleted ? (
                  <div className="w-6 h-6 rounded-full bg-green-500/20 flex items-center justify-center">
                    <svg
                      className="w-4 h-4 text-green-500"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2.5}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  </div>
                ) : isRunning ? (
                  <div className="relative">
                    {/* Pulsing background */}
                    <div
                      className={`absolute inset-0 rounded-full ${agent?.color} opacity-30 animate-ping`}
                      style={{ animationDuration: '1.5s' }}
                    />
                    {/* Spinning ring */}
                    <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : step.status === 'error' ? (
                  <div className="w-6 h-6 rounded-full bg-red-500/20 flex items-center justify-center">
                    <svg
                      className="w-4 h-4 text-red-500"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </div>
                ) : (
                  <div className="w-5 h-5 rounded-full bg-gray-600 opacity-50" />
                )}
              </div>

              {/* Agent color indicator */}
              <div className="relative">
                <span
                  className={`
                    block w-2.5 h-2.5 rounded-full transition-all duration-300
                    ${agent?.color}
                    ${isRunning ? 'animate-pulse' : ''}
                    ${!isRunning && !isCompleted ? 'opacity-40' : ''}
                  `}
                />
                {isRunning && (
                  <span
                    className={`absolute inset-0 w-2.5 h-2.5 rounded-full ${agent?.color} animate-ping opacity-75`}
                  />
                )}
              </div>

              {/* Description */}
              <div className="flex-1">
                <span
                  className={`text-sm transition-colors duration-300 ${
                    isRunning
                      ? 'text-white font-medium'
                      : isCompleted
                      ? 'text-gray-400 line-through'
                      : 'text-gray-500'
                  }`}
                >
                  {step.description}
                </span>
              </div>

              {/* Status label */}
              {isRunning && (
                <span className="text-xs text-blue-400 animate-pulse">
                  Running...
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
