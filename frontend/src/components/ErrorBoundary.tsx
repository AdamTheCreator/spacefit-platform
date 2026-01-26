import { Component, type ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
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
      return <DefaultErrorFallback onReset={() => this.setState({ hasError: false, error: null })} />;
    }
    return this.props.children;
  }
}

function DefaultErrorFallback({ onReset }: { onReset: () => void }) {
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
        <p className="text-sm text-industrial-muted mb-6">
          An unexpected error occurred. You can try again or go back to the home page.
        </p>
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
