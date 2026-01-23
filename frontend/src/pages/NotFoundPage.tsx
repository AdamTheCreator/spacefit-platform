import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';

export function NotFoundPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();

  return (
    <div className="min-h-screen bg-industrial dark flex flex-col">
      {/* Grid pattern overlay */}
      <div className="fixed inset-0 grid-pattern opacity-30 pointer-events-none" aria-hidden="true" />

      {/* Header bar */}
      <header className="relative z-10 border-b border-industrial p-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <Link to="/" className="font-mono text-sm font-medium tracking-wider uppercase text-industrial">
            SPACEFIT
          </Link>
          <span className="label-technical">SYSTEM STATUS</span>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 flex items-center justify-center p-8 relative z-10">
        <div className="max-w-2xl w-full text-center">
          {/* Error code display */}
          <div className="mb-12">
            <div className="inline-block relative">
              {/* Corner markers */}
              <span className="corner-marker corner-marker-tl" aria-hidden="true" />
              <span className="corner-marker corner-marker-tr" aria-hidden="true" />
              <span className="corner-marker corner-marker-bl" aria-hidden="true" />
              <span className="corner-marker corner-marker-br" aria-hidden="true" />

              <div className="px-12 py-8 border border-industrial-subtle">
                <span className="font-mono text-[120px] font-bold leading-none text-industrial-muted tracking-tight">
                  404
                </span>
              </div>
            </div>
          </div>

          {/* Status message */}
          <div className="card-industrial mb-8">
            <div className="card-industrial-header">
              <span className="card-industrial-title">Error Report</span>
              <span className="status-indicator status-indicator-error">Offline</span>
            </div>

            <div className="space-y-4 text-left">
              <div className="data-grid" style={{ gridTemplateColumns: '1fr 2fr' }}>
                <div>
                  <div className="data-label">Status Code</div>
                  <div className="data-value text-error">404</div>
                </div>
                <div>
                  <div className="data-label">Description</div>
                  <div className="text-industrial">Page Not Found</div>
                </div>
              </div>

              <p className="text-industrial-secondary text-sm leading-relaxed">
                The requested resource could not be located on this server.
                This may be due to an incorrect URL, a moved page, or a broken link.
              </p>
            </div>
          </div>

          {/* Accent bar decoration */}
          <div className="accent-bar mb-8" aria-hidden="true">
            <div className="accent-bar-segment" />
            <div className="accent-bar-segment active" />
            <div className="accent-bar-segment" />
            <div className="accent-bar-segment active" />
            <div className="accent-bar-segment" />
          </div>

          {/* Action buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <button
              onClick={() => navigate(-1)}
              className="btn-industrial"
              aria-label="Go back to previous page"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M19 12H5M12 19l-7-7 7-7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Go Back
            </button>

            <Link
              to={user ? '/chat' : '/login'}
              className="btn-industrial-primary"
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
      <footer className="relative z-10 border-t border-industrial p-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <span className="label-technical">SpaceFit AI v0.1</span>
          <span className="font-mono text-xs text-industrial-muted tabular-nums">
            {new Date().toISOString().split('T')[0]}
          </span>
        </div>
      </footer>
    </div>
  );
}

export default NotFoundPage;
