import { useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;

export function SocialLoginButtons() {
  const [showTooltip, setShowTooltip] = useState<string | null>(null);

  const handleGoogleLogin = () => {
    if (!GOOGLE_CLIENT_ID) {
      setShowTooltip('google');
      setTimeout(() => setShowTooltip(null), 3000);
      return;
    }
    window.location.href = `${API_URL}/api/v1/auth/google`;
  };

  const handleSSOLogin = () => {
    setShowTooltip('sso');
    setTimeout(() => setShowTooltip(null), 3000);
  };

  return (
    <div className="space-y-2">
      <div className="relative">
        <button
          type="button"
          onClick={handleGoogleLogin}
          aria-label="Continue with Google"
          className="btn-industrial w-full py-3 bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)]"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" aria-hidden="true">
            <path
              fill="currentColor"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="currentColor"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="currentColor"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              fill="currentColor"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          Google
        </button>
        {showTooltip === 'google' && (
          <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-2 bg-[var(--bg-tertiary)] border border-industrial text-industrial-secondary text-xs font-mono whitespace-nowrap z-10">
            Google SSO not configured
          </div>
        )}
      </div>

      <div className="relative">
        <button
          type="button"
          onClick={handleSSOLogin}
          aria-label="Continue with Company SSO"
          className="btn-industrial w-full py-3"
        >
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z" />
          </svg>
          Company SSO
        </button>
        {showTooltip === 'sso' && (
          <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-2 bg-[var(--bg-tertiary)] border border-industrial text-industrial-secondary text-xs font-mono whitespace-nowrap z-10">
            Configure SSO in settings after login
          </div>
        )}
      </div>
    </div>
  );
}
