import { useState, useEffect } from 'react';
import type { AgentType, WorkflowStep } from '../../types/chat';

interface AnalysisProcessingViewProps {
  workflowSteps: WorkflowStep[];
  activeAgentType: AgentType | null;
  isProcessing: boolean;
  analysisTarget?: string | null;
}

export function AnalysisProcessingView({
  workflowSteps,
  activeAgentType: _activeAgentType,
  isProcessing,
  analysisTarget,
}: AnalysisProcessingViewProps) {
  const [showReassurance, setShowReassurance] = useState(false);

  useEffect(() => {
    if (!isProcessing) {
      setShowReassurance(false);
      return;
    }
    const timer = setTimeout(() => setShowReassurance(true), 10000);
    return () => clearTimeout(timer);
  }, [isProcessing]);

  const completedCount = workflowSteps.filter(s => s.status === 'completed').length;
  const totalCount = workflowSteps.length;
  const hasSteps = totalCount > 0;

  // Find the currently running step description
  const runningStep = workflowSteps.find(s => s.status === 'running');
  const phaseText = runningStep?.description || 'Initializing analysis...';

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center max-w-md mx-auto animate-fade-in">
      {/* Space Goose icon with pulse ring */}
      <div className="relative mb-8">
        <img src="/spacegoose-logo.png" alt="" className="w-14 h-14 rounded-full object-cover shadow-lg shadow-[var(--accent)]/20" />
        <span className="absolute inset-0 rounded-full border-2 border-[var(--accent)]/40 animate-pulse-slow" />
      </div>

      {/* Heading */}
      <h3 className="text-xl font-semibold text-industrial mb-2">
        {analysisTarget ? `Analyzing ${analysisTarget}...` : 'Running analysis...'}
      </h3>

      {/* Phase text */}
      <p className="text-sm text-industrial-muted mb-6 transition-opacity duration-300">
        {phaseText}
      </p>

      {/* Progress bar */}
      <div className="w-full max-w-xs h-1.5 bg-[var(--bg-tertiary)] rounded-full overflow-hidden mb-8">
        {hasSteps ? (
          <div
            className="h-full bg-[var(--accent)] rounded-full transition-all duration-500 ease-out"
            style={{ width: `${(completedCount / totalCount) * 100}%` }}
          />
        ) : (
          <div className="h-full w-full animate-indeterminate-progress" />
        )}
      </div>

      {/* Workflow step list */}
      {hasSteps && (
        <div className="w-full text-left space-y-1.5">
          {workflowSteps.map((step, i) => {
            const isRunning = step.status === 'running';
            const isCompleted = step.status === 'completed';

            return (
              <div
                key={step.id}
                className={`flex items-center gap-3 px-4 py-2 rounded-lg text-sm transition-colors animate-step-fade-in ${
                  isRunning ? 'bg-[var(--accent-subtle)]' : ''
                }`}
                style={{ animationDelay: `${i * 80}ms` }}
              >
                {/* Status indicator */}
                {isCompleted ? (
                  <svg className="w-4 h-4 flex-shrink-0 text-[var(--color-success)]" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                ) : isRunning ? (
                  <span className="w-4 h-4 flex-shrink-0 rounded-full border-2 border-[var(--accent)] border-t-transparent animate-spin" />
                ) : (
                  <span className="w-4 h-4 flex-shrink-0 rounded-full border-2 border-[var(--border-default)]" />
                )}

                {/* Description */}
                <span className={isCompleted ? 'text-industrial-muted' : isRunning ? 'text-industrial font-medium' : 'text-industrial-muted'}>
                  {step.description}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Reassurance text */}
      {showReassurance && (
        <p className="text-xs text-industrial-muted mt-6 animate-fade-in">
          Pulling data from connected sources — this usually takes 15-30 seconds
        </p>
      )}
    </div>
  );
}
