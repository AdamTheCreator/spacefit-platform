import { useNavigate, Navigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';

/* ─── Static data ─── */
const TRUST_LOGOS = ['NORTHSTAR CAP', 'Harbor & Oak', 'MERIDIAN', 'Copperfield', 'STUDIO 34'];

const VALUE_PROPS = [
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>
    ),
    title: 'Search with intent',
    desc: 'Filter by yield, cap rate, zoning, or your own saved criteria. Every property is graded against your portfolio thesis automatically.',
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3v18h18"/><path d="m7 14 4-4 3 3 5-6"/></svg>
    ),
    title: 'Signals, not noise',
    desc: 'Market pulse, comp drift, and lease expirations surface as opportunities \u2014 not a 40-tab dashboard you never open.',
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2v4m0 12v4M4.9 4.9l2.8 2.8m8.6 8.6 2.8 2.8M2 12h4m12 0h4M4.9 19.1l2.8-2.8m8.6-8.6 2.8-2.8"/></svg>
    ),
    title: 'Workflow that flies',
    desc: 'Underwriting, outreach, diligence, and close \u2014 everything lives on one timeline. Your team, your pipeline, one altitude.',
    accent: true,
  },
];

const FEATURE_CHECKS = [
  'Live comp tracking with 30-day drift alerts',
  'Underwriting models that update as assumptions change',
  'Portfolio heatmap \u2014 see concentration and drift at a glance',
];

const SEARCH_CHECKS = [
  'Custom thesis matching \u2014 your rules, scored automatically',
  'Shared saved searches across your whole acquisitions team',
  'One-click comparison \u2014 side-by-side underwriting in seconds',
];

const METRICS = [
  { val: '$48B', label: 'In property value tracked' },
  { val: '12,400', label: 'Deals underwritten last quarter' },
  { val: '7\u00d7', label: 'Faster diligence on average' },
  { val: '98.6%', label: 'Customer retention' },
];

const MASCOTS = [
  { src: '/mascots/goose-planner.webp', name: 'The Planner', desc: 'Greets you in onboarding and in new projects \u2014 blueprint always in hand.' },
  { src: '/mascots/goose-engineer.webp', name: 'The Engineer', desc: 'Shows up in settings, integrations, and anywhere you\u2019re configuring the ship.' },
  { src: '/mascots/goose-planet.webp', name: 'The Navigator', desc: 'Your empty-state friend \u2014 keeps watch whenever a search returns no hits.' },
  { src: '/mascots/goose-launch.webp', name: 'The Launch', desc: 'Celebrates with you when a deal closes or a milestone ships.' },
];

const SEARCH_RESULTS = [
  { addr: 'Elm Grove Apartments \u2014 124 units', sub: 'Austin, TX \u00b7 1998 \u00b7 Score 92', price: '$24.4M', gradient: 'linear-gradient(135deg, var(--color-mist), var(--color-orbit))' },
  { addr: 'Harper & Ninth \u2014 96 units', sub: 'Nashville, TN \u00b7 2004 \u00b7 Score 88', price: '$18.9M', gradient: 'linear-gradient(135deg, #E5B85C, #FF8A3D)' },
  { addr: 'Cypress Yards \u2014 210 units', sub: 'Tampa, FL \u00b7 2012 \u00b7 Score 84', price: '$38.0M', gradient: 'linear-gradient(135deg, #1F3556, #3A5BA0)' },
  { addr: 'The Mercer \u2014 142 units', sub: 'Raleigh, NC \u00b7 2007 \u00b7 Score 81', price: '$29.7M', gradient: 'linear-gradient(135deg, #A7C7F7, #3A5BA0)' },
];

const NAV_LINKS = ['Product', 'Intelligence', 'Workflow', 'Pricing', 'Customers'];

const CheckIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12l4 4L19 6" strokeLinecap="round" strokeLinejoin="round"/></svg>
);

/* ─── Landing page ─── */
export function LandingPage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthStore();

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div style={{ background: 'var(--color-offwhite)', color: 'var(--color-neutral-700)', fontFamily: "var(--font-sans)" }}>
      {/* ═══ STICKY NAV ═══ */}
      <nav style={{
        position: 'sticky', top: 0, zIndex: 30,
        backdropFilter: 'blur(14px)', WebkitBackdropFilter: 'blur(14px)',
        background: 'rgba(245,241,232,0.82)',
        borderBottom: '1px solid var(--border-default)',
      }}>
        <div style={{ maxWidth: 1280, margin: '0 auto', padding: '16px 32px', display: 'flex', alignItems: 'center', gap: 40 }}>
          <a href="/" onClick={e => { e.preventDefault(); navigate('/'); }} style={{ display: 'inline-flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
            <img src="/spacegoose-logo.png" alt="Space Goose" width={40} height={40} style={{ borderRadius: '50%', objectFit: 'cover' }} />
            <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 20, color: 'var(--color-neutral-900)', letterSpacing: '0.02em' }}>SPACE GOOSE</span>
          </a>
          <div style={{ display: 'flex', gap: 28, flex: 1, fontSize: 14, fontWeight: 500 }} className="hidden md:flex">
            {NAV_LINKS.map(l => (
              <a key={l} href={`#${l.toLowerCase()}`} style={{ color: 'var(--color-neutral-700)', textDecoration: 'none' }}
                onMouseOver={e => (e.currentTarget.style.color = 'var(--color-neutral-900)')}
                onMouseOut={e => (e.currentTarget.style.color = 'var(--color-neutral-700)')}
              >{l}</a>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button onClick={() => navigate('/login')} className="btn-ghost btn-sm">Sign in</button>
            <button onClick={() => navigate('/register')} className="btn-primary btn-sm">Launch app</button>
          </div>
        </div>
      </nav>

      {/* ═══ HERO ═══ */}
      <section style={{ position: 'relative', padding: '72px 0 40px', overflow: 'hidden' }}>
        <div className="star" style={{ top: 80, left: '8%' }} />
        <div className="star sm mist" style={{ top: 180, left: '4%' }} />
        <div className="star gold" style={{ top: 320, left: '12%' }} />
        <div className="star sm" style={{ top: 440, left: '2%' }} />
        <div className="star sm mist" style={{ top: 120, right: '45%' }} />

        <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 32px' }}>
          <div className="landing-hero-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1.15fr', gap: 56, alignItems: 'center' }}>
            <div>
              <span className="pill pill-gold" style={{ marginBottom: 24 }}>
                <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor"><circle cx="5" cy="5" r="3"/></svg>
                New &middot; Insight engine 2.0
              </span>
              <h1 style={{
                fontFamily: 'var(--font-display)', fontSize: 68, lineHeight: 1.02,
                letterSpacing: '-0.025em', fontWeight: 700, color: 'var(--color-neutral-900)', marginTop: 0,
              }}>
                Mission control for{' '}
                <em style={{
                  fontStyle: 'normal', color: 'var(--color-orbit)', position: 'relative',
                }}>
                  real estate
                  <span style={{
                    position: 'absolute', left: 0, right: 0, bottom: 6, height: 8,
                    background: 'var(--color-gold)', opacity: 0.45, zIndex: -1, borderRadius: 2,
                  }} />
                </em>.
              </h1>
              <p style={{ fontSize: 19, lineHeight: 1.55, color: 'var(--color-neutral-700)', marginTop: 24, maxWidth: 520 }}>
                Space Goose gives professional investors, brokers, and operators a calm, connected view of every property &mdash; from search to underwriting to portfolio ops. Less tab-hopping. More confident decisions.
              </p>
              <div style={{ display: 'flex', gap: 12, marginTop: 32 }}>
                <button onClick={() => navigate('/register')} className="btn-accent btn-lg">
                  Start free trial
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8h10m0 0L9 4m4 4l-4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></svg>
                </button>
                <button onClick={() => navigate('/demo')} className="btn-secondary btn-lg">See a live tour</button>
              </div>
              <div style={{ display: 'flex', gap: 24, marginTop: 28, fontSize: 13, color: 'var(--color-neutral-700)', alignItems: 'center' }}>
                <span><span style={{ color: '#2F7A3B', fontWeight: 600 }}>&#10003;</span> 14-day trial</span>
                <span><span style={{ color: '#2F7A3B', fontWeight: 600 }}>&#10003;</span> No card required</span>
                <span><span style={{ color: '#2F7A3B', fontWeight: 600 }}>&#10003;</span> SOC 2 Type II</span>
              </div>
            </div>

            {/* Hero scene */}
            <div style={{ marginRight: -40 }}>
              <div style={{
                position: 'relative', aspectRatio: '5 / 4',
                background: 'radial-gradient(ellipse at 60% 40%, #FDFAF0 0%, var(--color-cream) 60%, var(--color-offwhite) 100%)',
                borderRadius: 32, border: '1px solid var(--border-default)', overflow: 'hidden',
                boxShadow: 'var(--shadow-md)',
              }}>
                <div className="orbit-ring" style={{ width: '120%', height: '120%', top: '-10%', left: '-10%', borderColor: 'rgba(58,91,160,0.18)' }} />
                <div className="orbit-ring" style={{ width: '70%', height: '70%', top: '15%', left: '15%', borderColor: 'rgba(229,184,92,0.25)' }} />
                <img src="/mascots/landing-hero.png" alt="Goose engineers assembling the Space Goose spaceship"
                  style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'contain', objectPosition: 'center' }} />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ CUSTOMER LOGOS ═══ */}
      <section style={{ padding: '40px 0 20px', borderTop: '1px solid var(--border-default)', borderBottom: '1px solid var(--border-default)', background: 'var(--color-cream)' }}>
        <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 32px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 40, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--color-neutral-700)', opacity: 0.6 }}>
            Trusted by forward-looking real estate teams
          </span>
          {TRUST_LOGOS.map(name => (
            <span key={name} style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 18, color: 'var(--color-neutral-900)', opacity: 0.55, letterSpacing: '-0.01em' }}>
              {name}
            </span>
          ))}
        </div>
      </section>

      {/* ═══ VALUE PROPS ═══ */}
      <section id="product" style={{ padding: '96px 0 40px' }}>
        <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 32px' }}>
          <div style={{ textAlign: 'center', maxWidth: 680, margin: '0 auto 56px' }}>
            <span className="eyebrow">Why Space Goose</span>
            <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 44, lineHeight: 1.1, marginTop: 12, color: 'var(--color-neutral-900)' }}>
              Real estate moves fast. Your tooling shouldn't slow it down.
            </h2>
            <p style={{ marginTop: 16, fontSize: 17, color: 'var(--color-neutral-700)', lineHeight: 1.55 }}>
              Replace seven spreadsheets and three portals with one workspace built around how real deals actually get done.
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20 }} className="landing-value-grid">
            {VALUE_PROPS.map(v => (
              <div key={v.title} style={{
                background: v.accent ? 'var(--color-neutral-900)' : '#fff',
                border: `1px solid ${v.accent ? 'var(--color-neutral-900)' : 'var(--border-default)'}`,
                borderRadius: 20, padding: 28, position: 'relative',
                color: v.accent ? 'var(--color-neutral-100)' : undefined,
              }}>
                <div style={{
                  width: 44, height: 44, borderRadius: 12,
                  background: v.accent ? 'rgba(255,255,255,0.08)' : 'var(--color-neutral-100)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: v.accent ? 'var(--color-gold)' : 'var(--color-orbit)',
                  marginBottom: 20,
                }}>
                  {v.icon}
                </div>
                <h3 style={{ fontSize: 20, fontWeight: 600, marginBottom: 8, color: v.accent ? '#fff' : undefined, fontFamily: 'var(--font-display)' }}>
                  {v.title}
                </h3>
                <p style={{ fontSize: 14.5, color: v.accent ? 'rgba(255,255,255,0.72)' : 'var(--color-neutral-700)', lineHeight: 1.55, margin: 0 }}>
                  {v.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ FEATURE: INSIGHT ENGINE ═══ */}
      <section id="intelligence">
        <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 32px' }}>
          {/* Row 1: Copy left, mockup right */}
          <div className="landing-feature-row" style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: 64, alignItems: 'center', padding: '80px 0' }}>
            <div>
              <span className="eyebrow">Insight engine</span>
              <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 38, marginTop: 12, lineHeight: 1.12, color: 'var(--color-neutral-900)' }}>
                See the whole sky, not just the tab you're on.
              </h2>
              <p style={{ marginTop: 16, fontSize: 16, lineHeight: 1.6, color: 'var(--color-neutral-700)' }}>
                Space Goose unifies MLS, CoStar-class market data, permits, zoning, and your firm's own proprietary notes into one live picture. The signal you need is where you expect it.
              </p>
              <ul style={{ marginTop: 20, padding: 0, listStyle: 'none', display: 'grid', gap: 10 }}>
                {FEATURE_CHECKS.map(text => (
                  <li key={text} style={{ display: 'flex', gap: 12, alignItems: 'flex-start', fontSize: 15, color: 'var(--color-neutral-700)' }}>
                    <span style={{ flexShrink: 0, marginTop: 2, color: 'var(--accent)' }}><CheckIcon /></span>
                    <span>{text}</span>
                  </li>
                ))}
              </ul>
              <div style={{ marginTop: 28 }}>
                <button onClick={() => navigate('/register')} className="btn-primary">Explore the dashboard &rarr;</button>
              </div>
            </div>

            {/* Portfolio mockup */}
            <div style={{
              position: 'relative', background: 'var(--color-neutral-100)', border: '1px solid var(--border-default)',
              borderRadius: 20, padding: 28, boxShadow: 'var(--shadow-sm)',
            }}>
              <div style={{ background: '#fff', borderRadius: 12, border: '1px solid var(--border-default)', padding: 20 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-default)', paddingBottom: 14, marginBottom: 16 }}>
                  <h4 style={{ fontSize: 14, color: 'var(--color-neutral-900)', margin: 0, fontFamily: 'var(--font-display)' }}>Portfolio &mdash; 24 properties</h4>
                  <span className="pill pill-mist">Live</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10, marginBottom: 16 }}>
                  {[
                    { label: 'NOI YTD', val: '$4.2M', delta: '+6.8%', down: false },
                    { label: 'Avg cap rate', val: '5.7%', delta: '+0.4pt', down: false },
                    { label: 'Occupancy', val: '93%', delta: '\u22121.1pt', down: true },
                  ].map(s => (
                    <div key={s.label} style={{ background: 'var(--color-cream)', borderRadius: 10, padding: 12 }}>
                      <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-neutral-700)' }}>{s.label}</div>
                      <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, color: 'var(--color-neutral-900)', fontSize: 20, marginTop: 4 }}>{s.val}</div>
                      <div style={{ fontSize: 11, color: s.down ? '#B64535' : '#2F7A3B', marginTop: 2 }}>{s.delta}</div>
                    </div>
                  ))}
                </div>
                {/* Chart area */}
                <div style={{ background: 'var(--color-cream)', borderRadius: 10, padding: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--color-neutral-700)', marginBottom: 8 }}>
                    <span>Portfolio NOI &middot; rolling 12mo</span>
                    <span className="mono">USD</span>
                  </div>
                  <svg viewBox="0 0 300 80" style={{ width: '100%', display: 'block' }}>
                    <defs>
                      <linearGradient id="ga" x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0" stopColor="#3A5BA0" stopOpacity={0.28}/>
                        <stop offset="1" stopColor="#3A5BA0" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <path d="M0,60 L25,55 L50,58 L75,48 L100,52 L125,40 L150,42 L175,32 L200,36 L225,24 L250,26 L275,18 L300,12 L300,80 L0,80 Z" fill="url(#ga)"/>
                    <path d="M0,60 L25,55 L50,58 L75,48 L100,52 L125,40 L150,42 L175,32 L200,36 L225,24 L250,26 L275,18 L300,12" stroke="#3A5BA0" strokeWidth="2" fill="none"/>
                    <circle cx="300" cy="12" r="3.5" fill="#FF8A3D"/>
                  </svg>
                </div>
              </div>
            </div>
          </div>

          {/* Row 2: Mockup left, copy right */}
          <div className="landing-feature-row" id="workflow" style={{ display: 'grid', gridTemplateColumns: '1fr 1.1fr', gap: 64, alignItems: 'center', padding: '80px 0' }}>
            {/* Search mockup */}
            <div style={{
              position: 'relative', background: 'var(--color-neutral-100)', border: '1px solid var(--border-default)',
              borderRadius: 20, padding: 28, boxShadow: 'var(--shadow-sm)',
            }}>
              <div style={{ background: '#fff', borderRadius: 12, border: '1px solid var(--border-default)', overflow: 'hidden' }}>
                <div style={{ display: 'flex', gap: 8, padding: 12, borderBottom: '1px solid var(--border-default)', background: 'var(--color-cream)', alignItems: 'center' }}>
                  <div style={{ flex: 1, background: '#fff', borderRadius: 8, border: '1px solid var(--border-strong)', padding: '8px 12px', fontSize: 13, color: 'var(--color-neutral-900)', display: 'flex', gap: 8, alignItems: 'center' }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>
                    Multifamily &middot; Sun Belt &middot; 80+ units
                  </div>
                  <span className="filter-chip active">Thesis: Core+</span>
                  <span className="filter-chip">Cap &ge; 6%</span>
                  <span className="filter-chip">Yr built &ge; 1990</span>
                </div>
                {SEARCH_RESULTS.map((r, i) => (
                  <div key={i} style={{
                    display: 'grid', gridTemplateColumns: '48px 1fr auto', gap: 12,
                    padding: 12, borderBottom: i < SEARCH_RESULTS.length - 1 ? '1px solid var(--border-default)' : 'none',
                    alignItems: 'center',
                  }}>
                    <div style={{
                      width: 48, height: 48, borderRadius: 8, background: r.gradient,
                      position: 'relative', overflow: 'hidden',
                    }}>
                      <div style={{
                        position: 'absolute', inset: 0,
                        backgroundImage: 'repeating-linear-gradient(45deg, rgba(255,255,255,0.12) 0 4px, transparent 4px 8px)',
                      }} />
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-neutral-900)' }}>{r.addr}</div>
                      <div style={{ fontSize: 11, color: 'var(--color-neutral-700)' }}>{r.sub}</div>
                    </div>
                    <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, color: 'var(--color-neutral-900)', fontSize: 14 }}>{r.price}</div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <span className="eyebrow">Search &amp; evaluate</span>
              <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 38, marginTop: 12, lineHeight: 1.12, color: 'var(--color-neutral-900)' }}>
                From a 12,000-result listing page to ten that matter.
              </h2>
              <p style={{ marginTop: 16, fontSize: 16, lineHeight: 1.6, color: 'var(--color-neutral-700)' }}>
                Stop scrolling. Space Goose's search ranks every property against your fund's criteria, your target IRR, and your team's past decisions &mdash; so you only spend time on deals worth your time.
              </p>
              <ul style={{ marginTop: 20, padding: 0, listStyle: 'none', display: 'grid', gap: 10 }}>
                {SEARCH_CHECKS.map(text => (
                  <li key={text} style={{ display: 'flex', gap: 12, alignItems: 'flex-start', fontSize: 15, color: 'var(--color-neutral-700)' }}>
                    <span style={{ flexShrink: 0, marginTop: 2, color: 'var(--accent)' }}><CheckIcon /></span>
                    <span>{text}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ METRICS BAND ═══ */}
      <section style={{ padding: '72px 0', borderTop: '1px solid var(--border-default)', borderBottom: '1px solid var(--border-default)', background: 'var(--color-cream)' }}>
        <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 32px', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 40 }} className="landing-metrics-grid">
          {METRICS.map(m => (
            <div key={m.label}>
              <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 48, color: 'var(--color-neutral-900)', letterSpacing: '-0.02em' }}>{m.val}</div>
              <div style={{ fontSize: 13, color: 'var(--color-neutral-700)', marginTop: 4 }}>{m.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ═══ PERSONALITY / MASCOTS ═══ */}
      <section id="customers" style={{ background: 'var(--color-neutral-900)', color: 'var(--color-neutral-100)', padding: '96px 0', position: 'relative', overflow: 'hidden' }}>
        <div className="star mist" style={{ top: 80, left: '10%' }} />
        <div className="star gold" style={{ top: 140, left: '20%' }} />
        <div className="star sm mist" style={{ top: 260, left: '6%' }} />
        <div className="star mist" style={{ top: 80, right: '15%' }} />
        <div className="star sm gold" style={{ top: 220, right: '10%' }} />

        <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 32px' }}>
          <span className="eyebrow" style={{ color: 'var(--color-gold)' }}>Built by a small flock</span>
          <h2 style={{ color: '#fff', fontFamily: 'var(--font-display)', fontSize: 42, maxWidth: 640, marginTop: 12 }}>
            Powerful tools don't have to feel cold.
          </h2>
          <p style={{ color: 'rgba(255,255,255,0.75)', fontSize: 17, lineHeight: 1.6, maxWidth: 560, marginTop: 18 }}>
            Space Goose is a serious workspace wrapped in a little bit of joy. Our mascot crew shows up when it helps &mdash; on your first day, when a search runs dry, or when a deal crosses the finish line.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 20, marginTop: 64 }} className="landing-mascot-grid">
            {MASCOTS.map(m => (
              <div key={m.name} style={{
                background: '#13233B', borderRadius: 18, padding: 20,
                border: '1px solid #1F3556', textAlign: 'left',
              }}>
                <img src={m.src} alt={m.name} style={{
                  width: '100%', aspectRatio: '1 / 1', objectFit: 'contain',
                  background: 'var(--color-cream)', borderRadius: 12,
                }} />
                <h4 style={{ color: '#fff', fontFamily: 'var(--font-display)', fontSize: 15, marginTop: 14, fontWeight: 600 }}>{m.name}</h4>
                <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: 12, marginTop: 4, lineHeight: 1.4 }}>{m.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ TESTIMONIAL ═══ */}
      <section style={{ padding: '96px 0' }}>
        <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 32px' }}>
          <div style={{
            background: '#fff', border: '1px solid var(--border-default)', borderRadius: 24,
            padding: 56, maxWidth: 900, margin: '0 auto',
          }}>
            <blockquote style={{
              fontFamily: 'var(--font-display)', fontSize: 28, fontWeight: 500,
              lineHeight: 1.35, color: 'var(--color-neutral-900)', margin: '0 0 28px',
              letterSpacing: '-0.01em',
            }}>
              "We used to run deals through three disconnected tools and a truly cursed spreadsheet. Space Goose replaced all of it &mdash; and we actually enjoy using it. Our acquisitions cycle is down 40%."
            </blockquote>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <div className="avatar avatar-lg">MC</div>
              <div>
                <div style={{ fontWeight: 600, color: 'var(--color-neutral-900)', fontSize: 15 }}>Maya Castellanos</div>
                <div style={{ fontSize: 13, color: 'var(--color-neutral-700)' }}>Head of Acquisitions &middot; Northstar Capital</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ CTA BAND ═══ */}
      <section style={{ padding: '88px 0', textAlign: 'center' }}>
        <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 32px' }}>
          <div style={{
            background: 'var(--color-neutral-900)', color: '#fff', borderRadius: 28,
            padding: '72px 40px', position: 'relative', overflow: 'hidden',
          }}>
            <div className="star mist" style={{ top: 30, left: '10%' }} />
            <div className="star gold" style={{ top: 80, left: '18%' }} />
            <div className="star sm mist" style={{ top: 160, left: '12%' }} />
            <div className="star mist" style={{ top: 50, left: '38%' }} />

            <h2 style={{ color: '#fff', fontFamily: 'var(--font-display)', fontSize: 48, lineHeight: 1.08, margin: 0 }}>
              Ready for clear skies?
            </h2>
            <p style={{ color: 'rgba(255,255,255,0.75)', fontSize: 18, marginTop: 16, maxWidth: 520, marginLeft: 'auto', marginRight: 'auto' }}>
              Start a 14-day trial. No credit card. The geese will set everything up for you.
            </p>
            <div style={{ marginTop: 32, display: 'flex', gap: 12, justifyContent: 'center' }}>
              <button onClick={() => navigate('/register')} className="btn-accent btn-lg">Launch Space Goose</button>
              <button className="btn-lg" style={{
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                gap: 8, padding: '12px 24px', fontSize: 14, fontWeight: 500,
                background: 'rgba(255,255,255,0.06)', color: '#fff',
                border: '1px solid rgba(255,255,255,0.2)', borderRadius: 'var(--radius-sm)',
                cursor: 'pointer', textDecoration: 'none',
              }}>Talk to a human</button>
            </div>
            <img src="/mascots/goose-launch.webp" alt=""
              style={{ position: 'absolute', right: 24, bottom: -10, width: 200, height: 200, objectFit: 'contain', opacity: 0.96 }} />
          </div>
        </div>
      </section>

      {/* ═══ FOOTER ═══ */}
      <footer style={{ padding: '64px 0 32px', borderTop: '1px solid var(--border-default)', background: 'var(--color-offwhite)' }}>
        <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 32px' }}>
          <div className="landing-footer-grid" style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr', gap: 40 }}>
            <div>
              <a href="/" onClick={e => { e.preventDefault(); navigate('/'); }} style={{ display: 'inline-flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
                <img src="/spacegoose-logo.png" alt="Space Goose" width={40} height={40} style={{ borderRadius: '50%', objectFit: 'cover' }} />
                <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 20, color: 'var(--color-neutral-900)', letterSpacing: '0.02em' }}>SPACE GOOSE</span>
              </a>
              <p style={{ marginTop: 16, fontSize: 14, color: 'var(--color-neutral-700)', maxWidth: 280, lineHeight: 1.55 }}>
                Playful spatial intelligence for the people who move the built world.
              </p>
            </div>
            {[
              { title: 'Product', links: [{ label: 'Dashboard', to: '/dashboard' }, { label: 'Search', to: '/search' }, { label: 'Analytics', to: '/analytics' }, { label: 'Workflow', to: '/workflow' }] },
              { title: 'Company', links: [{ label: 'About' }, { label: 'Careers' }, { label: 'Press' }, { label: 'Contact' }] },
              { title: 'Resources', links: [{ label: 'Docs' }, { label: 'Changelog' }, { label: 'API' }, { label: 'Status' }] },
              { title: 'Legal', links: [{ label: 'Privacy' }, { label: 'Terms' }, { label: 'Security' }] },
            ].map(col => (
              <div key={col.title}>
                <h5 style={{ fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 600, color: 'var(--color-neutral-900)', marginBottom: 14, letterSpacing: '0.02em' }}>{col.title}</h5>
                {col.links.map(l => {
                  const dest = 'to' in l ? l.to : undefined;
                  return (
                    <a key={l.label}
                      href={dest || '#'}
                      onClick={dest ? (e => { e.preventDefault(); navigate(dest); }) : undefined}
                      style={{ display: 'block', color: 'var(--color-neutral-700)', textDecoration: 'none', fontSize: 14, lineHeight: 1.9 }}
                      onMouseOver={e => (e.currentTarget.style.color = 'var(--color-neutral-900)')}
                      onMouseOut={e => (e.currentTarget.style.color = 'var(--color-neutral-700)')}
                    >
                      {l.label}
                    </a>
                  );
                })}
              </div>
            ))}
          </div>
          <div style={{
            marginTop: 56, paddingTop: 24, borderTop: '1px solid var(--border-default)',
            display: 'flex', justifyContent: 'space-between', fontSize: 13, color: 'var(--color-neutral-700)',
          }}>
            <span>&copy; 2026 Space Goose. All rights reserved.</span>
            <span>Made by a very small, very serious flock</span>
          </div>
        </div>
      </footer>

      {/* ═══ Responsive overrides (injected as a style tag) ═══ */}
      <style>{`
        @media (max-width: 960px) {
          .landing-hero-grid { grid-template-columns: 1fr !important; gap: 40px !important; }
          .landing-hero-grid h1 { font-size: 48px !important; }
          .landing-hero-grid > div:last-child { margin-right: 0 !important; }
          .landing-value-grid { grid-template-columns: 1fr !important; }
          .landing-feature-row { grid-template-columns: 1fr !important; gap: 40px !important; }
          .landing-mascot-grid { grid-template-columns: repeat(2, 1fr) !important; }
          .landing-metrics-grid { grid-template-columns: repeat(2, 1fr) !important; gap: 24px !important; }
          .landing-footer-grid { grid-template-columns: 1fr 1fr !important; }
        }
        @media (max-width: 640px) {
          .landing-mascot-grid { grid-template-columns: 1fr !important; }
          .landing-metrics-grid { grid-template-columns: 1fr !important; }
          .landing-footer-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}

export default LandingPage;
