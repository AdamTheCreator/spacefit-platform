import { Component, type ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  /** If true, show a compact inline error instead of a full-page fallback */
  inline?: boolean;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      if (this.props.inline) {
        return (
          <InlineErrorFallback
            error={this.state.error}
            onReset={() => this.setState({ hasError: false, error: null })}
          />
        );
      }
      return (
        <DefaultErrorFallback
          error={this.state.error}
          onReset={() => this.setState({ hasError: false, error: null })}
        />
      );
    }
    return this.props.children;
  }
}

function InlineErrorFallback({ error, onReset }: { error: Error | null; onReset: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full p-6">
      <div className="w-12 h-12 bg-[var(--bg-error)] border border-[var(--color-error)]/20 rounded-2xl flex items-center justify-center mb-3">
        <svg className="w-6 h-6 text-[var(--color-error)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      </div>
      <h3 className="text-sm font-semibold text-industrial mb-1">Failed to load</h3>
      {error && (
        <div className="w-full max-w-sm mb-3">
          <p className="text-xs text-[var(--color-error)] text-center break-words">
            {error.message}
          </p>
          <details className="mt-2">
            <summary className="text-[11px] text-industrial-muted cursor-pointer hover:text-industrial-secondary">
              Show stack trace
            </summary>
            <pre className="mt-1 p-2 bg-[var(--bg-tertiary)] border border-[var(--border-subtle)] rounded-lg text-[10px] text-industrial-muted overflow-auto max-h-40 whitespace-pre-wrap break-words">
              {error.stack}
            </pre>
          </details>
        </div>
      )}
      <button onClick={onReset} className="btn-industrial text-xs">
        Try Again
      </button>
    </div>
  );
}

function DefaultErrorFallback({ error, onReset }: { error: Error | null; onReset: () => void }) {
  return (
    <div className="h-full flex items-center justify-center bg-[var(--bg-primary)]">
      <div className="text-center p-8 max-w-md">
        <div className="w-14 h-14 bg-[var(--bg-error)] border border-[var(--color-error)]/20 rounded-2xl flex items-center justify-center mx-auto mb-4">
          <svg className="w-7 h-7 text-[var(--color-error)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h2 className="text-base font-semibold text-industrial mb-2">Something went wrong</h2>
        <p className="text-sm text-industrial-muted mb-4">
          An unexpected error occurred. You can try again or go back to the home page.
        </p>
        {error && (
          <div className="mb-4 text-left">
            <p className="text-xs text-[var(--color-error)] text-center break-words mb-2">
              {error.message}
            </p>
            <details>
              <summary className="text-[11px] text-industrial-muted cursor-pointer hover:text-industrial-secondary text-center">
                Show stack trace
              </summary>
              <pre className="mt-1 p-3 bg-[var(--bg-tertiary)] border border-[var(--border-subtle)] rounded-lg text-[10px] text-industrial-muted overflow-auto max-h-48 whitespace-pre-wrap break-words">
                {error.stack}
              </pre>
            </details>
          </div>
        )}
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={onReset}
            className="btn-industrial"
          >
            Try Again
          </button>
          <a
            href="/"
            className="btn-industrial-primary"
          >
            Go Home
          </a>
        </div>
      </div>
    </div>
  );
}
