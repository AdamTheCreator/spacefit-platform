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
        <div className="flex items-center gap-3">
          <img src="/perigee-logo.png" alt="Perigee" width={50} height={50} className="rounded-full object-cover" />
          <span style={{ fontFamily: "'Sora', sans-serif", fontWeight: 700, fontSize: 22, letterSpacing: '0.04em' }}>PERIGEE</span>
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
      <section className="w-full px-6 md:px-12 lg:px-20 mb-6">
        <div className="flex justify-center">
          <img src="/mascots/landing-hero.png" alt="Perigee goose crew building a space station" className="w-full max-w-[1400px] object-contain" style={{ height: 'clamp(300px, 50vw, 700px)' }} />
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
