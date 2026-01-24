interface ThinkingIndicatorProps {
  isVisible: boolean;
}

export function ThinkingIndicator({ isVisible }: ThinkingIndicatorProps) {
  if (!isVisible) return null;

  return (
    <div className="flex items-start gap-3 mb-4 animate-fade-in">
      {/* Avatar with pulsing animation */}
      <div className="relative flex-shrink-0">
        <div className="w-10 h-10 bg-[var(--accent)] rounded-lg flex items-center justify-center">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className="w-5 h-5 text-[var(--color-neutral-900)]"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="3" />
            <path d="M12 2v4M12 18v4M2 12h4M18 12h4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
          </svg>
        </div>
        {/* Pulsing ring */}
        <div className="absolute inset-0 bg-[var(--accent)] rounded-lg opacity-30 animate-ping" aria-hidden="true" />
      </div>

      {/* Thinking bubble */}
      <div className="bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-lg px-4 py-3 max-w-md shadow-sm">
        <div className="flex items-center gap-3">
          {/* Animated dots */}
          <div className="flex gap-1.5" role="status" aria-label="Loading">
            <span className="thinking-dot w-2 h-2 rounded-full bg-[var(--accent)]" />
            <span className="thinking-dot w-2 h-2 rounded-full bg-[var(--accent)]" style={{ animationDelay: '0.15s' }} />
            <span className="thinking-dot w-2 h-2 rounded-full bg-[var(--accent)]" style={{ animationDelay: '0.3s' }} />
          </div>
          <span className="text-sm text-industrial-secondary">SpaceFit is thinking...</span>
        </div>

        {/* Shimmer bar */}
        <div className="mt-3 processing-bar" />
      </div>
    </div>
  );
}
