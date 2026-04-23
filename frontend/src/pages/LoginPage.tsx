import { useNavigate, useLocation, Link, Navigate } from 'react-router-dom';
import { LoginForm } from '../components/Auth/LoginForm';
import { SocialLoginButtons } from '../components/Auth/SocialLoginButtons';
import { useAuthStore } from '../stores/authStore';

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated } = useAuthStore();

  const from = (location.state as { from?: Location })?.from?.pathname || '/dashboard';

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const handleSuccess = () => {
    navigate(from, { replace: true });
  };

  return (
    <div className="min-h-screen flex" style={{ background: '#F8F8F7' }}>
      {/* Left Panel — Space Goose branding */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 relative overflow-hidden" style={{ background: 'linear-gradient(160deg, #0F1B2D 0%, #1A2D4A 100%)' }}>
        {/* Decorative orbit */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-[0.06]" viewBox="0 0 600 800" fill="none">
          <ellipse cx="300" cy="400" rx="400" ry="250" stroke="white" strokeWidth="1" />
          <ellipse cx="300" cy="400" rx="250" ry="160" stroke="white" strokeWidth="0.5" />
        </svg>

        {/* Logo */}
        <Link to="/" className="relative z-10 flex items-center gap-2.5">
          <img src="/spacegoose-logo.png" alt="Space Goose" width={32} height={32} className="rounded-full object-cover" />
          <span style={{ fontFamily: "'Sora', sans-serif", fontWeight: 700, fontSize: 16, letterSpacing: '0.04em', color: 'white' }}>SPACE GOOSE</span>
        </Link>

        {/* Tagline + mascot */}
        <div className="relative z-10 space-y-6">
          <p className="text-xs font-semibold tracking-[0.2em] uppercase" style={{ color: '#E5A840' }}>Real Estate Intelligence</p>
          <h1 className="text-4xl font-bold tracking-tight leading-tight text-white" style={{ fontFamily: "'Sora', sans-serif" }}>
            Playful intelligence
            <br />
            for modern real estate.
          </h1>
          <p className="text-base max-w-md leading-relaxed" style={{ color: 'rgba(255,255,255,0.6)' }}>
            AI-powered site selection, market analysis, and deal management for retail real estate professionals.
          </p>

          {/* Stats bar */}
          <div className="flex gap-10 pt-8" style={{ borderTop: '1px solid rgba(255,255,255,0.1)' }}>
            <div>
              <div className="text-2xl font-bold tabular-nums" style={{ color: '#E5A840' }}>2.4M+</div>
              <div className="text-xs mt-1" style={{ color: 'rgba(255,255,255,0.4)' }}>Properties</div>
            </div>
            <div>
              <div className="text-2xl font-bold tabular-nums" style={{ color: '#E5A840' }}>850+</div>
              <div className="text-xs mt-1" style={{ color: 'rgba(255,255,255,0.4)' }}>Markets</div>
            </div>
            <div>
              <div className="text-2xl font-bold tabular-nums" style={{ color: '#E5A840' }}>99.2%</div>
              <div className="text-xs mt-1" style={{ color: 'rgba(255,255,255,0.4)' }}>Uptime</div>
            </div>
          </div>
        </div>

        {/* Mascot */}
        <div className="relative z-10 flex items-end gap-4">
          <img src="/mascots/goose-solar.webp" alt="" className="h-28 object-contain opacity-90" />
          <span className="text-xs mb-2" style={{ color: 'rgba(255,255,255,0.3)' }}>
            v{import.meta.env.VITE_APP_VERSION ?? '2.4'}
          </span>
        </div>
      </div>

      {/* Right Panel — Login form on light background */}
      <div className="flex-1 flex items-center justify-center p-4 sm:p-8 overflow-y-auto">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center justify-center gap-2.5 mb-8">
            <img src="/spacegoose-logo.png" alt="Space Goose" width={28} height={28} className="rounded-full object-cover" />
            <span style={{ fontFamily: "'Sora', sans-serif", fontWeight: 700, fontSize: 16, color: '#0F1B2D' }}>SPACE GOOSE</span>
          </div>

          <div className="mb-8 text-center lg:text-left">
            <h2 className="text-2xl font-semibold mb-2" style={{ color: '#0F1B2D', fontFamily: "'Sora', sans-serif" }}>
              Welcome back
            </h2>
            <p className="text-sm" style={{ color: '#737169' }}>Sign in to continue to your account</p>
          </div>

          <div className="rounded-2xl border p-6" style={{ background: 'white', borderColor: '#E0DFDD', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
            <SocialLoginButtons />

            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full" style={{ borderTop: '1px solid #E0DFDD' }} />
              </div>
              <div className="relative flex justify-center">
                <span className="px-3 text-xs" style={{ background: 'white', color: '#A3A19D' }}>Or continue with email</span>
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
