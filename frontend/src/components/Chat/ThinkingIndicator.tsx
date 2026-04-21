import { AGENTS, type AgentType } from '../../types/chat';

interface ThinkingIndicatorProps {
  isVisible: boolean;
  activeAgentType?: AgentType | null;
}

export function ThinkingIndicator({ isVisible, activeAgentType }: ThinkingIndicatorProps) {
  if (!isVisible) return null;

  const activeAgentName = activeAgentType ? AGENTS[activeAgentType]?.name : null;

  return (
    <div className="w-full group animate-fade-in" role="status" aria-live="polite" aria-label="Perigee is working on your request">
      <div className="chat-stage px-4 py-2">
        <div className="flex gap-4 sm:gap-6 items-start">
          <div className="relative flex-shrink-0 pt-1">
            <div className="absolute inset-0 rounded-full bg-[var(--accent)]/20 blur-md animate-pulse" aria-hidden="true" />
            <img src="/perigee-logo.png" alt="" className="relative w-7 h-7 rounded-full object-cover shadow-md shadow-[var(--accent)]/30" />
            <div className="absolute -inset-1 rounded-full border border-[var(--accent)]/30 animate-ping" aria-hidden="true" />
          </div>

          <div className="flex-1 min-w-0 rounded-2xl border border-[var(--accent)]/15 bg-[linear-gradient(135deg,var(--bg-elevated)_0%,var(--accent-subtle)_100%)] px-4 py-3 shadow-sm">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-industrial">
                {activeAgentName || 'Perigee Assistant'}
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-[var(--bg-primary)]/70 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--accent)]">
                Live
                <span className="block w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse" />
              </span>
            </div>

            <div className="mt-2 flex items-center gap-3 text-sm text-industrial-secondary">
              <div className="flex gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[var(--accent)] animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 rounded-full bg-[var(--accent)] animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 rounded-full bg-[var(--accent)] animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
              <span>Mapping the next response...</span>
            </div>

            <div className="mt-3 overflow-hidden rounded-full bg-[var(--bg-primary)]/70">
              <div className="animate-indeterminate-progress h-1.5" />
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              <span className="rounded-full border border-[var(--border-default)] bg-[var(--bg-primary)]/75 px-2.5 py-1 text-[11px] text-industrial-secondary animate-pulse">
                Reviewing context
              </span>
              <span className="rounded-full border border-[var(--border-default)] bg-[var(--bg-primary)]/75 px-2.5 py-1 text-[11px] text-industrial-secondary animate-pulse" style={{ animationDelay: '200ms' }}>
                Coordinating agents
              </span>
              <span className="rounded-full border border-[var(--border-default)] bg-[var(--bg-primary)]/75 px-2.5 py-1 text-[11px] text-industrial-secondary animate-pulse" style={{ animationDelay: '400ms' }}>
                Drafting answer
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
