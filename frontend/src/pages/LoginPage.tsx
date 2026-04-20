import { useNavigate, useLocation } from 'react-router-dom';
import { LoginForm } from '../components/Auth/LoginForm';
import { SocialLoginButtons } from '../components/Auth/SocialLoginButtons';

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as { from?: Location })?.from?.pathname || '/';

  const handleSuccess = () => {
    navigate(from, { replace: true });
  };

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] dark flex">
      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-[var(--bg-secondary)] flex-col justify-between p-12 relative overflow-hidden">
        {/* Subtle gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-br from-[var(--accent-subtle)] to-transparent opacity-50" />

        {/* Logo */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="w-3 h-3 rounded-sm bg-[var(--accent)]" />
          <span className="text-sm font-semibold tracking-wide text-industrial">
            Perigee
          </span>
        </div>

        {/* Tagline */}
        <div className="relative z-10 space-y-6">
          <h1 className="text-4xl font-bold tracking-tight text-industrial leading-tight">
            Commercial Real Estate
            <br />
            <span className="text-[var(--accent)]">Intelligence Platform</span>
          </h1>
          <p className="text-base text-industrial-secondary max-w-md leading-relaxed">
            AI-powered site selection, market analysis, and deal management for retail real estate professionals.
          </p>

          {/* Stats bar */}
          <div className="flex gap-10 pt-8 border-t border-[var(--border-subtle)]">
            <div>
              <div className="text-2xl font-bold text-[var(--accent)] tabular-nums">2.4M+</div>
              <div className="text-xs text-industrial-muted mt-1">Properties</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-[var(--accent)] tabular-nums">850+</div>
              <div className="text-xs text-industrial-muted mt-1">Markets</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-[var(--accent)] tabular-nums">99.2%</div>
              <div className="text-xs text-industrial-muted mt-1">Uptime</div>
            </div>
          </div>
        </div>

        {/* Version */}
        <div className="relative z-10 text-xs text-industrial-muted">
          v{import.meta.env.VITE_APP_VERSION}
        </div>
      </div>

      {/* Right Panel - Login Form */}
      <div className="flex-1 flex items-center justify-center p-4 sm:p-8 overflow-y-auto">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center justify-center gap-2 mb-8">
            <div className="w-2 h-2 rounded-sm bg-[var(--accent)]" />
            <span className="text-sm font-semibold tracking-wide text-industrial">
              Perigee
            </span>
          </div>

          <div className="mb-8 text-center lg:text-left">
            <h2 className="text-2xl font-semibold text-industrial mb-2">
              Welcome back
            </h2>
            <p className="text-sm text-industrial-secondary">Sign in to continue to your account</p>
          </div>

          <div className="bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] shadow-sm p-6">
            <SocialLoginButtons />

            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-[var(--border-subtle)]" />
              </div>
              <div className="relative flex justify-center">
                <span className="px-3 bg-[var(--bg-elevated)] text-xs text-industrial-muted">Or continue with email</span>
              </div>
            </div>

            <LoginForm
              onSuccess={handleSuccess}
              onSwitchToRegister={() => navigate('/register')}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
