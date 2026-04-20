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
            <span className="text-sm font-semibold text-industrial">Perigee</span>
          </Link>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 flex items-center justify-center p-8 relative z-10">
        <div className="max-w-md w-full text-center">
          {/* Off-course: Navigator goose + planet */}
          <div className="mb-6">
            <img
              src="/mascots/goose-planet.png"
              alt=""
              className="w-48 h-48 mx-auto object-contain select-none"
              draggable={false}
            />
            <h1 className="text-5xl font-bold text-industrial-muted mt-2 tracking-tight">404</h1>
          </div>

          {/* Status message */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-industrial mb-2">Off-course</h2>
            <p className="text-sm text-industrial-secondary leading-relaxed">
              This page isn't on our star chart. Check the URL or head back to mission control.
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
          <span className="text-xs text-industrial-muted">Perigee v{import.meta.env.VITE_APP_VERSION}</span>
        </div>
      </footer>
    </div>
  );
}

export default NotFoundPage;
