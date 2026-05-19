import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Loader2 } from 'lucide-react';
import api from '../lib/axios';
import { useAuthStore } from '../stores/authStore';

export function WelcomePage() {
  const navigate = useNavigate();
  const { user, setUser } = useAuthStore();
  const [loading, setLoading] = useState(false);

  const handleContinue = async () => {
    setLoading(true);
    try {
      await api.post('/onboarding/complete');
      if (user) {
        setUser({ ...user, has_completed_onboarding: true });
      }
      navigate('/dashboard', { replace: true });
    } catch (error) {
      console.error('Failed to complete welcome:', error);
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center px-4">
      <div className="w-full max-w-xl text-center">
        <img
          src="/mascots/goose-planner.webp"
          alt=""
          aria-hidden="true"
          className="w-32 h-32 mx-auto mb-6 object-contain select-none"
          draggable={false}
        />
        <h1 className="font-display text-[28px] font-semibold tracking-tight text-industrial mb-3">
          Welcome to Space Goose{user?.first_name ? `, ${user.first_name}` : ''}.
        </h1>
        <p className="text-[15px] leading-relaxed text-industrial-secondary mb-2 max-w-md mx-auto">
          You&apos;re ready to chat with the goose crew about properties, tenants, and
          outreach right away — we&apos;ll cover your first queries on the platform AI.
        </p>
        <p className="text-[13px] leading-relaxed text-industrial-muted mb-8 max-w-md mx-auto">
          When you want unlimited usage on your own billing, drop in an Anthropic,
          OpenAI, or Gemini key from Settings. Everything else — imports, integrations,
          team preferences — can wait until you need it.
        </p>
        <button
          onClick={handleContinue}
          disabled={loading}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white font-semibold text-sm transition-colors shadow-sm disabled:opacity-60"
        >
          {loading ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              Opening mission control…
            </>
          ) : (
            <>
              Continue to Space Goose
              <ArrowRight size={16} />
            </>
          )}
        </button>
      </div>
    </div>
  );
}

export default WelcomePage;
