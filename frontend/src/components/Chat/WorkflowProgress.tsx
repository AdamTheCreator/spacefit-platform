import type { WorkflowStep } from '../../types/chat';
import { AGENTS } from '../../types/chat';

interface WorkflowProgressProps {
  steps: WorkflowStep[];
}

export function WorkflowProgress({ steps }: WorkflowProgressProps) {
  if (steps.length === 0) return null;

  const runningSteps = steps.filter((s) => s.status === 'running');
  const completedSteps = steps.filter((s) => s.status === 'completed');
  const progress = steps.length > 0 ? (completedSteps.length / steps.length) * 100 : 0;
  const allComplete = completedSteps.length === steps.length;

  return (
    <div className="bg-[var(--bg-elevated)] border border-[var(--border-subtle)] rounded-xl p-4 mb-4 overflow-hidden shadow-sm">
      {/* Header with progress bar */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-industrial">Workflow Progress</h3>
        <span className="text-xs text-industrial-muted">
          {completedSteps.length} of {steps.length} complete
        </span>
      </div>

      {/* Progress bar */}
      <div
        className="h-1.5 bg-[var(--bg-tertiary)] rounded-full mb-4 overflow-hidden"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(progress)}
        aria-label={`Workflow progress: ${completedSteps.length} of ${steps.length} steps complete`}
      >
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out relative ${
            allComplete ? 'bg-[var(--color-success)]' : 'bg-[var(--accent)]'
          }`}
          style={{ width: `${progress}%` }}
        >
          {runningSteps.length > 0 && (
            <div className="absolute inset-0 bg-white/20 animate-pulse-soft rounded-full" aria-hidden="true" />
          )}
        </div>
      </div>

      {/* Steps */}
      <div className="space-y-1">
        {steps.map((step) => {
          const agent = AGENTS[step.agentType];
          const isRunning = step.status === 'running';
          const isCompleted = step.status === 'completed';
          const isError = step.status === 'error';

          return (
            <div
              key={step.id}
              className={`
                flex items-center gap-3 p-2.5 rounded-lg transition-all duration-200
                ${isRunning ? 'bg-[var(--accent-subtle)]' : ''}
                ${isCompleted ? 'opacity-70' : ''}
              `}
            >
              {/* Status indicator */}
              <div className="flex items-center justify-center w-5 h-5 relative flex-shrink-0">
                {isCompleted ? (
                  <div className="w-5 h-5 rounded-full bg-[var(--bg-success)] flex items-center justify-center">
                    <svg
                      className="w-3 h-3 text-[var(--color-success)]"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      aria-hidden="true"
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
                  <div className="relative w-5 h-5">
                    <div className="w-5 h-5 rounded-full border-2 border-[var(--accent)] border-t-transparent animate-spin" />
                  </div>
                ) : isError ? (
                  <div className="w-5 h-5 rounded-full bg-[var(--bg-error)] flex items-center justify-center">
                    <svg
                      className="w-3 h-3 text-[var(--color-error)]"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      aria-hidden="true"
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
                  <div className="w-4 h-4 rounded-full border-2 border-[var(--border-default)] opacity-50" />
                )}
              </div>

              {/* Agent color indicator */}
              <div className="relative flex-shrink-0">
                <span
                  className={`
                    block w-2 h-2 rounded-full transition-all duration-200
                    ${agent?.color}
                    ${isRunning ? 'animate-pulse-soft' : ''}
                    ${!isRunning && !isCompleted ? 'opacity-40' : ''}
                  `}
                />
                {isRunning && (
                  <span
                    className={`absolute inset-0 w-2 h-2 rounded-full ${agent?.color} animate-ping opacity-50`}
                    aria-hidden="true"
                  />
                )}
              </div>

              {/* Description */}
              <div className="flex-1 min-w-0">
                <span
                  className={`text-sm transition-colors duration-200 ${
                    isRunning
                      ? 'text-industrial font-medium'
                      : isCompleted
                      ? 'text-industrial-muted line-through'
                      : 'text-industrial-muted'
                  }`}
                >
                  {step.description}
                </span>
              </div>

              {/* Status label */}
              {isRunning && (
                <span className="text-xs font-medium text-[var(--accent)] animate-pulse-soft flex-shrink-0">
                  Running
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
