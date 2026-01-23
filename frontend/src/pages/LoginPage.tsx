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
    <div className="min-h-screen bg-industrial-secondary dark flex">
      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-industrial flex-col justify-between p-12 relative overflow-hidden">
        {/* Grid pattern overlay */}
        <div className="absolute inset-0 grid-pattern opacity-30" />

        {/* Corner markers */}
        <div className="absolute top-8 left-8 w-4 h-4 border-l-2 border-t-2 border-[var(--accent)]" />
        <div className="absolute top-8 right-8 w-4 h-4 border-r-2 border-t-2 border-[var(--accent)]" />
        <div className="absolute bottom-8 left-8 w-4 h-4 border-l-2 border-b-2 border-[var(--accent)]" />
        <div className="absolute bottom-8 right-8 w-4 h-4 border-r-2 border-b-2 border-[var(--accent)]" />

        {/* Logo */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="w-3 h-3 bg-[var(--accent)]" />
          <span className="font-mono text-sm font-bold tracking-[0.2em] uppercase text-industrial">
            SpaceFit
          </span>
        </div>

        {/* Tagline */}
        <div className="relative z-10 space-y-6">
          <h1 className="font-mono text-4xl font-bold tracking-tight text-industrial leading-tight">
            Commercial Real Estate
            <br />
            <span className="text-[var(--accent)]">Intelligence Platform</span>
          </h1>
          <p className="font-mono text-sm text-industrial-secondary max-w-md leading-relaxed">
            AI-powered site selection, market analysis, and deal management for retail real estate professionals.
          </p>

          {/* Stats bar */}
          <div className="flex gap-8 pt-8 border-t border-industrial">
            <div>
              <div className="data-number text-[var(--accent)]">2.4M+</div>
              <div className="label-technical mt-1">Properties</div>
            </div>
            <div>
              <div className="data-number text-[var(--accent)]">850+</div>
              <div className="label-technical mt-1">Markets</div>
            </div>
            <div>
              <div className="data-number text-[var(--accent)]">99.2%</div>
              <div className="label-technical mt-1">Uptime</div>
            </div>
          </div>
        </div>

        {/* Version */}
        <div className="relative z-10 label-technical">
          System v0.1.0 // Ready
        </div>
      </div>

      {/* Right Panel - Login Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center justify-center gap-2 mb-8">
            <div className="w-2 h-2 bg-[var(--accent)]" />
            <span className="font-mono text-xs font-bold tracking-[0.2em] uppercase text-industrial">
              SpaceFit
            </span>
          </div>

          <div className="mb-8">
            <h2 className="font-mono text-xl font-bold tracking-tight text-industrial mb-2">
              Access Terminal
            </h2>
            <p className="label-technical">Authentication Required</p>
          </div>

          <div className="card-industrial">
            <SocialLoginButtons />

            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-industrial-subtle" />
              </div>
              <div className="relative flex justify-center">
                <span className="px-3 bg-[var(--bg-elevated)] label-technical">Or continue with email</span>
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
