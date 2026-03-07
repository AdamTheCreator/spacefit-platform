import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';

export function NotFoundPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] dark flex flex-col">
      {/* Header bar */}
      <header className="relative z-10 border-b border-[var(--border-subtle)] p-4 bg-[var(--bg-secondary)]">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-sm bg-[var(--accent)]" />
            <span className="text-sm font-semibold text-industrial">SpaceFit</span>
          </Link>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 flex items-center justify-center p-8 relative z-10">
        <div className="max-w-md w-full text-center">
          {/* Error code display */}
          <div className="mb-8">
            <div className="w-24 h-24 mx-auto rounded-2xl bg-[var(--bg-error)] flex items-center justify-center mb-6">
              <svg className="w-12 h-12 text-[var(--color-error)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              </svg>
            </div>
            <h1 className="text-6xl font-bold text-industrial-muted mb-2">404</h1>
          </div>

          {/* Status message */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-industrial mb-2">Page not found</h2>
            <p className="text-sm text-industrial-secondary leading-relaxed">
              The page you're looking for doesn't exist or has been moved.
              Check the URL or navigate back to a working page.
            </p>
          </div>

          {/* Action buttons */}
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              onClick={() => navigate(-1)}
              className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg border border-[var(--border-default)] text-sm font-medium text-industrial hover:bg-[var(--hover-overlay)] transition-colors"
              aria-label="Go back to previous page"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M19 12H5M12 19l-7-7 7-7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Go Back
            </button>

            <Link
              to={user ? '/chat' : '/login'}
              className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-[var(--accent)] text-[var(--color-neutral-900)] text-sm font-medium hover:bg-[var(--accent-hover)] transition-colors shadow-sm"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" strokeLinecap="round" strokeLinejoin="round" />
                <polyline points="9,22 9,12 15,12 15,22" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {user ? 'Return Home' : 'Sign In'}
            </Link>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-[var(--border-subtle)] p-4">
        <div className="flex items-center justify-center max-w-7xl mx-auto">
          <span className="text-xs text-industrial-muted">SpaceFit v0.2.0</span>
        </div>
      </footer>
    </div>
  );
}

export default NotFoundPage;
