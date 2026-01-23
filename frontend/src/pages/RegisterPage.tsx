import { useNavigate } from 'react-router-dom';
import { RegisterForm } from '../components/Auth/RegisterForm';
import { SocialLoginButtons } from '../components/Auth/SocialLoginButtons';

export function RegisterPage() {
  const navigate = useNavigate();

  const handleSuccess = () => {
    navigate('/onboarding', { replace: true });
  };

  return (
    <div className="min-h-screen bg-industrial-secondary dark flex items-center justify-center px-4 py-12">
      {/* Grid pattern overlay */}
      <div className="fixed inset-0 grid-pattern opacity-20 pointer-events-none" />

      <div className="w-full max-w-md relative z-10">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2 mb-8">
          <div className="w-2 h-2 bg-[var(--accent)]" />
          <span className="font-mono text-xs font-bold tracking-[0.2em] uppercase text-industrial">
            SpaceFit
          </span>
        </div>

        <div className="mb-8">
          <h1 className="font-mono text-xl font-bold tracking-tight text-industrial mb-2 text-center">
            Create Account
          </h1>
          <p className="label-technical text-center">New user registration</p>
        </div>

        <div className="card-industrial">
          <SocialLoginButtons />

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-industrial-subtle" />
            </div>
            <div className="relative flex justify-center">
              <span className="px-3 bg-[var(--bg-elevated)] label-technical">Or register with email</span>
            </div>
          </div>

          <RegisterForm
            onSuccess={handleSuccess}
            onSwitchToLogin={() => navigate('/login')}
          />
        </div>
      </div>
    </div>
  );
}
