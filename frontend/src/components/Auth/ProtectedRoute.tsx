import { useEffect, useRef } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';

export function ProtectedRoute() {
  const { isAuthenticated, isLoading, checkAuth, user } = useAuthStore();
  const location = useLocation();
  const hasCheckedAuth = useRef(false);

  useEffect(() => {
    // Only check auth once per session, and only if we don't already have a valid user
    if (!hasCheckedAuth.current && !user) {
      hasCheckedAuth.current = true;
      checkAuth();
    }
  }, [checkAuth, user]);

  // Show loading only during initial auth check
  if (isLoading && !user) {
    return (
      <div className="min-h-screen bg-industrial dark flex items-center justify-center">
        <div className="flex flex-col items-center gap-6">
          <div className="relative">
            <div className="w-12 h-12 border border-[var(--border-color)]" />
            <div className="absolute inset-0 border-t-2 border-[var(--accent)] animate-spin" />
          </div>
          <div className="flex flex-col items-center gap-2">
            <p className="font-mono text-xs tracking-wider uppercase text-industrial-secondary">
              Authenticating
            </p>
            <div className="flex gap-1">
              <span className="w-1.5 h-1.5 bg-[var(--accent)] animate-pulse" />
              <span className="w-1.5 h-1.5 bg-[var(--accent)] animate-pulse [animation-delay:150ms]" />
              <span className="w-1.5 h-1.5 bg-[var(--accent)] animate-pulse [animation-delay:300ms]" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (user && !user.has_completed_onboarding && location.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />;
  }

  return <Outlet />;
}
