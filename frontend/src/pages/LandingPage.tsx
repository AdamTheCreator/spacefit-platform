import { useNavigate, Navigate } from 'react-router-dom';
import { ArrowRight, BarChart3, Target, Users } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';

const NAV_LINKS = ['Product', 'Solutions', 'Resources', 'Company'];

const VALUE_PROPS = [
  { icon: BarChart3, title: 'Market intelligence', desc: 'at your fingertips' },
  { icon: Target, title: 'Precision insights', desc: 'that close deals' },
  { icon: Users, title: 'Built for teams', desc: 'who move fast' },
];

const TRUST_LOGOS = ['SUMMIT', 'NORTHFIELD', 'REDWOOD', 'HARBOR', 'VERTEX'];

const FEATURE_CARDS: { mascot: string; title: string; desc: string; accent: string }[] = [
  { mascot: '/mascots/goose-engineer.webp', title: 'BUILT TOOLS', desc: 'Powerful tools for real estate pros.', accent: '#3A5BA0' },
  { mascot: '/mascots/goose-planner.webp', title: 'SEE MORE', desc: 'Surface opportunities others miss.', accent: '#FF8A3D' },
  { mascot: '/mascots/goose-mechanic.webp', title: 'PLAN SMARTER', desc: 'Data-driven insights to confirm decisions.', accent: '#E5B85C' },
  { mascot: '/mascots/goose-planet.webp', title: 'REACH FURTHER', desc: 'From deals on Earth to dreams beyond.', accent: '#3A5BA0' },
];

export function LandingPage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthStore();

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="min-h-screen bg-white text-[var(--color-neutral-900)]" style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>
      {/* ─── Top Nav ─── */}
      <nav className="max-w-[1200px] mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <img src="/perigee-logo.png" alt="Perigee" width={28} height={28} className="rounded-full object-cover" />
          <span style={{ fontFamily: "'Sora', sans-serif", fontWeight: 700, fontSize: 16, letterSpacing: '0.04em' }}>PERIGEE</span>
        </div>
        <div className="hidden md:flex items-center gap-8">
          {NAV_LINKS.map(l => (
            <button key={l} className="text-sm text-neutral-600 hover:text-neutral-900 transition-colors">{l}</button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/login')} className="text-sm text-neutral-600 hover:text-neutral-900 transition-colors">Log in</button>
          <button onClick={() => navigate('/register')}
            className="text-sm font-semibold px-4 py-2 rounded-full text-white transition-colors"
            style={{ background: '#FF8A3D' }}>
            Get started
          </button>
        </div>
      </nav>

      {/* ─── Hero ─── */}
      <section className="max-w-[1200px] mx-auto px-6 pt-12 pb-4 text-center">
        <p className="text-xs font-semibold tracking-[0.2em] uppercase mb-4"
          style={{ color: '#3A5BA0' }}>
          Real Estate Intelligence
        </p>
        <h1 style={{
          fontFamily: "'Sora', sans-serif",
          fontSize: 'clamp(48px, 8vw, 80px)',
          fontWeight: 800,
          letterSpacing: '-0.03em',
          lineHeight: 1,
          color: '#0F1B2D',
          marginBottom: 20,
        }}>
          PERIGEE
        </h1>
        <p className="text-lg text-neutral-500 max-w-md mx-auto mb-8" style={{ lineHeight: 1.6 }}>
          Playful intelligence for<br />modern real estate.
        </p>
        <div className="flex items-center justify-center gap-3 mb-14">
          <button onClick={() => navigate('/register')}
            className="text-sm font-semibold px-6 py-3 rounded-full text-white transition-all hover:opacity-90"
            style={{ background: '#0F1B2D' }}>
            Get started
          </button>
          <button onClick={() => navigate('/demo')}
            className="text-sm font-semibold px-6 py-3 rounded-full border-2 transition-all hover:bg-neutral-50 flex items-center gap-2"
            style={{ borderColor: '#0F1B2D', color: '#0F1B2D' }}>
            See how it works <ArrowRight size={14} />
          </button>
        </div>
      </section>

      {/* ─── Hero Illustration ─── */}
      <section className="max-w-[900px] mx-auto px-6 mb-6">
        <div className="relative rounded-2xl overflow-hidden" style={{
          background: 'linear-gradient(180deg, #F0F4FA 0%, #E8EDF5 100%)',
          border: '1px solid #D8DFE9',
          padding: '40px 20px 20px',
        }}>
          {/* Space station scene with mascots */}
          <div className="flex items-end justify-center gap-2 relative" style={{ minHeight: 220 }}>
            <img src="/mascots/goose-engineer.webp" alt="" className="h-28 object-contain relative z-10" style={{ marginBottom: -4 }} />
            <img src="/mascots/goose-welder.webp" alt="" className="h-32 object-contain relative z-10" style={{ marginBottom: -4 }} />
            <div className="relative z-0 mx-4">
              {/* Stylized space station core */}
              <div className="relative">
                <img src="/mascots/goose-solar.webp" alt="" className="h-40 object-contain" />
              </div>
            </div>
            <img src="/mascots/goose-mechanic.webp" alt="" className="h-32 object-contain relative z-10" style={{ marginBottom: -4 }} />
            <img src="/mascots/goose-planner.webp" alt="" className="h-28 object-contain relative z-10" style={{ marginBottom: -4 }} />
          </div>
          {/* Decorative orbit lines */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 900 280" fill="none">
            <ellipse cx="450" cy="180" rx="380" ry="60" stroke="#C8D4E5" strokeWidth="1" strokeDasharray="6 4" opacity="0.5" />
            <ellipse cx="450" cy="160" rx="300" ry="45" stroke="#C8D4E5" strokeWidth="1" strokeDasharray="4 6" opacity="0.3" />
          </svg>
        </div>
      </section>

      {/* ─── Value Props ─── */}
      <section className="max-w-[800px] mx-auto px-6 py-10">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 text-center">
          {VALUE_PROPS.map(v => (
            <div key={v.title} className="flex flex-col items-center gap-3">
              <div className="w-11 h-11 rounded-xl flex items-center justify-center" style={{ background: '#F0F4FA' }}>
                <v.icon size={20} style={{ color: '#3A5BA0' }} />
              </div>
              <div>
                <p className="text-sm font-semibold text-neutral-900">{v.title}</p>
                <p className="text-sm text-neutral-500">{v.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ─── Trusted By ─── */}
      <section className="border-t border-b border-neutral-200 py-8 mb-12">
        <div className="max-w-[900px] mx-auto px-6 text-center">
          <p className="text-xs font-medium tracking-[0.12em] uppercase text-neutral-400 mb-6">
            Trusted by forward-thinking teams
          </p>
          <div className="flex items-center justify-center gap-10 flex-wrap">
            {TRUST_LOGOS.map(name => (
              <span key={name} className="text-sm font-bold tracking-[0.08em] uppercase" style={{ color: '#B0B8C4' }}>
                {name}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Feature Cards ─── */}
      <section className="max-w-[1100px] mx-auto px-6 pb-20">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {FEATURE_CARDS.map(card => (
            <div key={card.title}
              className="rounded-xl overflow-hidden border border-neutral-200 hover:shadow-lg transition-shadow"
              style={{ background: '#FAFAFA' }}>
              <div className="flex items-end justify-center pt-6 px-4" style={{ height: 160, background: `linear-gradient(180deg, ${card.accent}10, ${card.accent}05)` }}>
                <img src={card.mascot} alt="" className="h-32 object-contain" />
              </div>
              <div className="p-4">
                <h3 className="text-xs font-bold tracking-[0.1em] uppercase mb-1.5" style={{ color: card.accent }}>
                  {card.title}
                </h3>
                <p className="text-sm text-neutral-500 leading-relaxed">{card.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ─── Footer ─── */}
      <footer className="border-t border-neutral-200 py-8">
        <div className="max-w-[1200px] mx-auto px-6 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <img src="/perigee-logo.png" alt="Perigee" width={20} height={20} className="rounded-full object-cover" />
            <span className="text-xs text-neutral-400">&copy; 2026 Perigee. All rights reserved.</span>
          </div>
          <div className="flex items-center gap-6">
            <button className="text-xs text-neutral-400 hover:text-neutral-600">Privacy</button>
            <button className="text-xs text-neutral-400 hover:text-neutral-600">Terms</button>
            <button onClick={() => navigate('/login')} className="text-xs text-neutral-400 hover:text-neutral-600">Sign in</button>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default LandingPage;
