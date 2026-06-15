import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search as SearchIcon,
  Filter,
  LayoutGrid,
  List as ListIcon,
  Map as MapIcon,
  ArrowRight,
  Star,
} from 'lucide-react';
import { AppLayout } from '../components/Layout/AppLayout';

// ---------------------------------------------------------------------------
// Perigee / Space Goose palette — exact prototype values, kept local so this
// page reproduces the Claude design 1:1 regardless of token naming drift.
// ---------------------------------------------------------------------------
const C = {
  navy: '#0F1B2D',
  deep: '#1F3556',
  orbit: '#3A5BA0',
  mist: '#A7C7F7',
  moonlight: '#F2F5F9',
  offwhite: '#F5F1E8',
  cream: '#FBF8F0',
  slate: '#334155',
  orange: '#FF8A3D',
  gold: '#E5B85C',
  line: '#E5E2D6',
  lineStrong: '#D4D0C0',
  shadowSm: '0 1px 2px rgba(15,27,45,0.06)',
  shadowMd: '0 4px 14px rgba(15,27,45,0.08)',
  sora: "'Sora', system-ui, sans-serif",
  inter: "'Inter', system-ui, sans-serif",
} as const;

type Thesis = 'Core+' | 'Value-add' | 'Opportunistic';
type ViewMode = 'grid' | 'list' | 'map';

interface Prop {
  id: number;
  addr: string;
  city: string;
  price: string;
  cap: string;
  score: number;
  year: number;
  units: number;
  grad: string;
}

const PROPS: Prop[] = [
  { id: 1, addr: 'Elm Grove Apartments', city: 'Austin, TX', price: '$24.4M', cap: '6.8%', score: 92, year: 1998, units: 124, grad: 'linear-gradient(135deg,#A7C7F7,#3A5BA0)' },
  { id: 2, addr: 'Harper & Ninth', city: 'Nashville, TN', price: '$18.9M', cap: '6.4%', score: 88, year: 2004, units: 96, grad: 'linear-gradient(135deg,#E5B85C,#FF8A3D)' },
  { id: 3, addr: 'Cypress Yards', city: 'Tampa, FL', price: '$38.0M', cap: '6.1%', score: 84, year: 2012, units: 210, grad: 'linear-gradient(135deg,#1F3556,#3A5BA0)' },
  { id: 4, addr: 'The Mercer', city: 'Raleigh, NC', price: '$29.7M', cap: '5.9%', score: 81, year: 2007, units: 142, grad: 'linear-gradient(135deg,#3A5BA0,#A7C7F7)' },
  { id: 5, addr: 'North Loop 88', city: 'Minneapolis, MN', price: '$22.1M', cap: '6.7%', score: 79, year: 1996, units: 88, grad: 'linear-gradient(135deg,#0F1B2D,#3A5BA0)' },
  { id: 6, addr: 'Peachtree Commons', city: 'Atlanta, GA', price: '$41.6M', cap: '5.7%', score: 76, year: 2015, units: 234, grad: 'linear-gradient(135deg,#FF8A3D,#E5B85C)' },
];

// Score badge tone — ≥85 green, ≥80 gold, else navy (cards) / neutral (list).
function scorePillStyle(score: number, navyFallback: boolean): React.CSSProperties {
  if (score >= 85) return { background: '#E3F1E5', color: '#2F7A3B' };
  if (score >= 80) return { background: '#FBEFC8', color: '#8A6417' };
  return navyFallback
    ? { background: C.navy, color: C.offwhite }
    : { background: C.moonlight, color: C.deep };
}

const pillBase: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  padding: '4px 10px',
  borderRadius: 999,
  fontSize: 12,
  fontWeight: 500,
  fontFamily: C.inter,
};

const cardBase: React.CSSProperties = {
  background: '#fff',
  border: `1px solid ${C.line}`,
  borderRadius: 16,
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function SearchPage() {
  const [view, setView] = useState<ViewMode>('grid');
  const [thesis, setThesis] = useState<Thesis>('Core+');
  const navigate = useNavigate();
  const go = (id: number) => navigate(`/property/${id}`);

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto" style={{ background: C.offwhite }}>
        {/* Topbar-style header */}
        <div
          style={{
            padding: '20px 32px',
            borderBottom: `1px solid ${C.line}`,
            background: '#fff',
          }}
        >
          <h1 style={{ fontFamily: C.sora, fontSize: 22, fontWeight: 700, color: C.navy, letterSpacing: '-0.01em', margin: 0 }}>
            Search properties
          </h1>
          <p style={{ fontFamily: C.inter, fontSize: 13, color: C.slate, marginTop: 4 }}>
            12,402 assets available across your connected markets
          </p>
        </div>

        <div style={{ padding: '24px 32px' }}>
          {/* Filter bar */}
          <div style={{ ...cardBase, padding: 16, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: C.cream, borderRadius: 10, padding: '10px 14px', flex: '1 1 280px', minWidth: 240 }}>
              <SearchIcon size={16} color={C.slate} />
              <input
                style={{ border: 'none', background: 'transparent', outline: 'none', flex: 1, fontSize: 14, fontFamily: C.inter, color: C.navy }}
                placeholder="Multifamily · Sun Belt · 80+ units"
              />
            </div>

            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {(['Core+', 'Value-add', 'Opportunistic'] as Thesis[]).map((t) => (
                <button
                  key={t}
                  onClick={() => setThesis(t)}
                  style={{
                    background: thesis === t ? C.navy : '#fff',
                    color: thesis === t ? '#fff' : C.slate,
                    border: `1px solid ${thesis === t ? C.navy : C.lineStrong}`,
                    padding: '8px 14px',
                    fontSize: 13,
                    borderRadius: 999,
                    cursor: 'pointer',
                    fontFamily: C.inter,
                    fontWeight: 500,
                  }}
                >
                  Thesis: {t}
                </button>
              ))}
            </div>

            <span style={{ ...pillBase, background: C.moonlight, color: C.deep }}>Cap ≥ 6%</span>
            <span style={{ ...pillBase, background: C.moonlight, color: C.deep }}>Yr ≥ 1990</span>
            <span style={{ ...pillBase, background: C.moonlight, color: C.deep }}>Units ≥ 80</span>

            <button
              style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: 'transparent', color: C.navy, border: 'none', padding: '8px 14px', fontSize: 13, fontWeight: 500, fontFamily: C.inter, borderRadius: 12, cursor: 'pointer' }}
            >
              <Filter size={14} /> More filters
            </button>

            <div style={{ marginLeft: 'auto', display: 'flex', gap: 4, background: C.cream, padding: 4, borderRadius: 10 }}>
              <ViewToggle active={view === 'grid'} onClick={() => setView('grid')}><LayoutGrid size={16} /></ViewToggle>
              <ViewToggle active={view === 'list'} onClick={() => setView('list')}><ListIcon size={16} /></ViewToggle>
              <ViewToggle active={view === 'map'} onClick={() => setView('map')}><MapIcon size={16} /></ViewToggle>
            </div>
          </div>

          {/* Results header */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <div style={{ fontSize: 14, color: C.slate, fontFamily: C.inter }}>
              <b style={{ color: C.navy }}>6</b> matches · sorted by{' '}
              <span style={{ color: C.navy, fontWeight: 500 }}>thesis score</span>
            </div>
            <button
              style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: 'transparent', color: C.navy, border: `1px solid ${C.lineStrong}`, padding: '8px 14px', fontSize: 13, fontWeight: 500, fontFamily: C.inter, borderRadius: 12, cursor: 'pointer' }}
            >
              Save this search
            </button>
          </div>

          {/* Body */}
          {view === 'map' ? (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 16, minHeight: 520 }}>
              <div style={{ position: 'relative', borderRadius: 16, overflow: 'hidden', background: 'linear-gradient(180deg, #E8F0FD, #F2F5F9)', border: `1px solid ${C.line}` }}>
                <svg viewBox="0 0 400 300" style={{ width: '100%', height: '100%', display: 'block' }}>
                  <path d="M0,180 Q80,120 160,160 T320,140 T400,180 L400,300 L0,300 Z" fill="rgba(167,199,247,0.35)" />
                  <path d="M0,220 Q100,180 200,200 T400,220 L400,300 L0,300 Z" fill="rgba(58,91,160,0.18)" />
                  {([
                    [80, 100, '#FF8A3D'], [140, 180, '#3A5BA0'], [230, 130, '#3A5BA0'],
                    [300, 200, '#3A5BA0'], [180, 230, '#E5B85C'], [340, 90, '#3A5BA0'],
                  ] as [number, number, string][]).map(([x, y, c], i) => (
                    <g key={i}>
                      <circle cx={x} cy={y} r="10" fill={c} opacity="0.2" />
                      <circle cx={x} cy={y} r="5" fill={c} />
                    </g>
                  ))}
                </svg>
                <div style={{ position: 'absolute', top: 14, left: 14, background: '#fff', borderRadius: 8, padding: '6px 12px', fontSize: 12, fontWeight: 600, color: C.navy, boxShadow: C.shadowSm, fontFamily: C.inter }}>
                  6 properties in view
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, overflow: 'auto', maxHeight: 540 }}>
                {PROPS.map((p) => <PropCard key={p.id} p={p} compact go={go} />)}
              </div>
            </div>
          ) : view === 'list' ? (
            <div style={{ ...cardBase, padding: 0, overflow: 'hidden' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '80px 2fr 1fr 0.8fr 0.8fr 0.8fr 80px', padding: '12px 20px', fontSize: 11, fontWeight: 600, color: C.slate, letterSpacing: '0.08em', textTransform: 'uppercase', borderBottom: `1px solid ${C.line}`, background: C.cream, fontFamily: C.inter }}>
                <span></span><span>Property</span><span>Location</span><span>Price</span><span>Cap</span><span>Score</span><span></span>
              </div>
              {PROPS.map((p) => (
                <div
                  key={p.id}
                  onClick={() => go(p.id)}
                  style={{ display: 'grid', gridTemplateColumns: '80px 2fr 1fr 0.8fr 0.8fr 0.8fr 80px', alignItems: 'center', padding: '14px 20px', borderBottom: `1px solid ${C.line}`, cursor: 'pointer' }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = C.cream; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                >
                  <div style={{ width: 56, height: 42, borderRadius: 8, background: p.grad, position: 'relative', overflow: 'hidden' }}>
                    <div style={{ position: 'absolute', inset: 0, backgroundImage: 'repeating-linear-gradient(45deg, rgba(255,255,255,0.12) 0 4px, transparent 4px 8px)' }} />
                  </div>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: C.navy, fontFamily: C.inter }}>{p.addr}</div>
                    <div style={{ fontSize: 11, color: C.slate, marginTop: 2, fontFamily: C.inter }}>{p.units} units · Built {p.year}</div>
                  </div>
                  <div style={{ fontSize: 13, color: C.slate, fontFamily: C.inter }}>{p.city}</div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: C.navy, fontFamily: C.sora }}>{p.price}</div>
                  <div style={{ fontSize: 13, color: C.slate, fontFamily: C.inter }}>{p.cap}</div>
                  <div><span style={{ ...pillBase, ...scorePillStyle(p.score, false), fontWeight: 600 }}>{p.score}</span></div>
                  <ArrowRight size={14} color={C.slate} />
                </div>
              ))}
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 16 }}>
              {PROPS.map((p) => <PropCard key={p.id} p={p} go={go} />)}
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}

// ---------------------------------------------------------------------------
// View toggle button
// ---------------------------------------------------------------------------

function ViewToggle({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: 8,
        borderRadius: 6,
        border: 'none',
        background: active ? '#fff' : 'transparent',
        cursor: 'pointer',
        color: C.navy,
        boxShadow: active ? C.shadowSm : 'none',
        display: 'inline-flex',
        alignItems: 'center',
      }}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Property card
// ---------------------------------------------------------------------------

function PropCard({ p, compact, go }: { p: Prop; compact?: boolean; go: (id: number) => void }) {
  return (
    <div
      onClick={() => go(p.id)}
      style={{ ...cardBase, padding: 0, overflow: 'hidden', cursor: 'pointer', transition: 'transform 0.12s, box-shadow 0.15s' }}
      onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = C.shadowMd; }}
      onMouseLeave={(e) => { e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = 'none'; }}
    >
      <div style={{ aspectRatio: compact ? '16/7' : '16/10', background: p.grad, position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', inset: 0, backgroundImage: 'repeating-linear-gradient(45deg, rgba(255,255,255,0.12) 0 6px, transparent 6px 12px)' }} />
        <span style={{ ...pillBase, ...scorePillStyle(p.score, true), position: 'absolute', top: 12, left: 12, fontWeight: 600 }}>
          Score {p.score}
        </span>
        <button
          onClick={(e) => e.stopPropagation()}
          style={{ position: 'absolute', top: 12, right: 12, width: 32, height: 32, borderRadius: 8, background: 'rgba(255,255,255,0.9)', border: 'none', cursor: 'pointer', color: C.navy, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}
        >
          <Star size={14} />
        </button>
      </div>
      <div style={{ padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: C.navy, fontFamily: C.sora }}>{p.addr}</div>
            <div style={{ fontSize: 12, color: C.slate, marginTop: 2, fontFamily: C.inter }}>{p.city} · {p.units} units · {p.year}</div>
          </div>
          <div style={{ fontSize: 16, fontWeight: 700, color: C.navy, fontFamily: C.sora }}>{p.price}</div>
        </div>
        <div style={{ display: 'flex', gap: 12, marginTop: 12, paddingTop: 12, borderTop: `1px solid ${C.line}`, fontSize: 12, color: C.slate, fontFamily: C.inter }}>
          <div><span style={{ color: C.navy, fontWeight: 600 }}>{p.cap}</span> cap</div>
          <div><span style={{ color: '#2F7A3B', fontWeight: 600 }}>+$240k</span> NOI est.</div>
          <div style={{ marginLeft: 'auto' }}>3d ago</div>
        </div>
      </div>
    </div>
  );
}

export default SearchPage;
