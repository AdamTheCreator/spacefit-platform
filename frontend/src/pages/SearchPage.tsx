import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search as SearchIcon,
  Grid3x3,
  List,
  Map as MapIcon,
  SlidersHorizontal,
  ArrowRight,
} from 'lucide-react';
import { AppLayout } from '../components/Layout/AppLayout';
import { PropertyCard, type PropertyCardData } from '../components/Search/PropertyCard';

type ViewMode = 'grid' | 'list' | 'map';
type Thesis = 'Core+' | 'Value-add' | 'Opportunistic';

const SAMPLE_PROPERTIES: PropertyCardData[] = [
  { id: 1, addr: 'Elm Grove Apartments', city: 'Austin, TX', price: '$24.4M', cap: '6.8%', score: 92, year: 1998, units: 124, grad: 'linear-gradient(135deg,#A7C7F7,#3A5BA0)' },
  { id: 2, addr: 'Harper & Ninth', city: 'Nashville, TN', price: '$18.9M', cap: '6.4%', score: 88, year: 2004, units: 96, grad: 'linear-gradient(135deg,#E5B85C,#FF8A3D)' },
  { id: 3, addr: 'Cypress Yards', city: 'Tampa, FL', price: '$38.0M', cap: '6.1%', score: 84, year: 2012, units: 210, grad: 'linear-gradient(135deg,#1F3556,#3A5BA0)' },
  { id: 4, addr: 'The Mercer', city: 'Raleigh, NC', price: '$29.7M', cap: '5.9%', score: 81, year: 2007, units: 142, grad: 'linear-gradient(135deg,#3A5BA0,#A7C7F7)' },
  { id: 5, addr: 'North Loop 88', city: 'Minneapolis, MN', price: '$22.1M', cap: '6.7%', score: 79, year: 1996, units: 88, grad: 'linear-gradient(135deg,#0F1B2D,#3A5BA0)' },
  { id: 6, addr: 'Peachtree Commons', city: 'Atlanta, GA', price: '$41.6M', cap: '5.7%', score: 76, year: 2015, units: 234, grad: 'linear-gradient(135deg,#FF8A3D,#E5B85C)' },
];

const MAP_PINS: Array<[number, number, string]> = [
  [80, 100, '#FF8A3D'],
  [140, 180, '#3A5BA0'],
  [230, 130, '#3A5BA0'],
  [300, 200, '#3A5BA0'],
  [180, 230, '#E5B85C'],
  [340, 90, '#3A5BA0'],
];

function scorePillClass(score: number): string {
  if (score >= 85) return 'bg-[#E3F1E5] text-[#2F7A3B]';
  if (score >= 80) return 'bg-[#FBEFC8] text-[#8A6417]';
  return 'bg-[var(--bg-tertiary)] text-industrial';
}

export function SearchPage() {
  const navigate = useNavigate();
  const [view, setView] = useState<ViewMode>('grid');
  const [thesis, setThesis] = useState<Thesis>('Core+');
  const [query, setQuery] = useState('Multifamily · Sun Belt · 80+ units');

  const handleCardClick = () => navigate('/projects');

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="px-8 py-6 max-w-[1400px]">
          {/* Filter bar */}
          <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-4 mb-5 flex items-center gap-2.5 flex-wrap">
            <div className="flex items-center gap-2 bg-[var(--bg-cream,var(--bg-tertiary))] rounded-lg px-3.5 py-2.5 flex-1 min-w-[240px]">
              <SearchIcon size={16} className="text-industrial-muted shrink-0" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="City, submarket, or address…"
                className="bg-transparent outline-none flex-1 text-sm text-industrial placeholder:text-industrial-muted"
              />
            </div>

            <div className="flex gap-1.5 flex-wrap">
              {(['Core+', 'Value-add', 'Opportunistic'] as Thesis[]).map((t) => (
                <button
                  key={t}
                  onClick={() => setThesis(t)}
                  className={`px-3.5 py-2 rounded-full text-[13px] font-medium border transition-colors ${
                    thesis === t
                      ? 'bg-[var(--color-neutral-900)] text-white border-[var(--color-neutral-900)]'
                      : 'bg-[var(--bg-secondary)] text-industrial-secondary border-[var(--border-strong)] hover:text-industrial'
                  }`}
                >
                  Thesis: {t}
                </button>
              ))}
            </div>

            {['Cap ≥ 6%', 'Yr ≥ 1990', 'Units ≥ 80'].map((p) => (
              <span
                key={p}
                className="inline-flex items-center px-3 py-1.5 rounded-full bg-[var(--bg-tertiary)] text-industrial-secondary text-[12px] font-medium"
              >
                {p}
              </span>
            ))}

            <button className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-industrial-secondary hover:bg-[var(--bg-tertiary)] hover:text-industrial transition-colors">
              <SlidersHorizontal size={14} />
              More filters
            </button>

            <div className="ml-auto flex gap-1 bg-[var(--bg-cream,var(--bg-tertiary))] p-1 rounded-lg">
              {(
                [
                  { id: 'grid' as const, Icon: Grid3x3, label: 'Grid view' },
                  { id: 'list' as const, Icon: List, label: 'List view' },
                  { id: 'map' as const, Icon: MapIcon, label: 'Map view' },
                ]
              ).map(({ id, Icon, label }) => (
                <button
                  key={id}
                  aria-label={label}
                  aria-pressed={view === id}
                  onClick={() => setView(id)}
                  className={`p-2 rounded-md text-industrial transition-all ${
                    view === id ? 'bg-[var(--bg-secondary)] shadow-sm' : 'hover:bg-[var(--bg-secondary)]/50'
                  }`}
                >
                  <Icon size={16} />
                </button>
              ))}
            </div>
          </div>

          {/* Results meta */}
          <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
            <div className="text-sm text-industrial-secondary">
              <b className="text-industrial">{SAMPLE_PROPERTIES.length}</b> matches · sorted by{' '}
              <span className="text-industrial font-medium">thesis score</span>
            </div>
            <button className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg border border-[var(--border-strong)] text-sm font-medium text-industrial hover:bg-[var(--bg-tertiary)] transition-colors">
              Save this search
            </button>
          </div>

          {/* Views */}
          {view === 'map' ? (
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-4 min-h-[520px]">
              <div
                className="relative rounded-2xl overflow-hidden border border-[var(--border-subtle)]"
                style={{ background: 'linear-gradient(180deg, #E8F0FD, #F2F5F9)' }}
              >
                <svg viewBox="0 0 400 300" className="w-full h-full block min-h-[520px]">
                  <path
                    d="M0,180 Q80,120 160,160 T320,140 T400,180 L400,300 L0,300 Z"
                    fill="rgba(167,199,247,0.35)"
                  />
                  <path
                    d="M0,220 Q100,180 200,200 T400,220 L400,300 L0,300 Z"
                    fill="rgba(58,91,160,0.18)"
                  />
                  {MAP_PINS.map(([x, y, c], i) => (
                    <g key={i}>
                      <circle cx={x} cy={y} r="10" fill={c} opacity="0.2" />
                      <circle cx={x} cy={y} r="5" fill={c} />
                    </g>
                  ))}
                </svg>
                <div className="absolute top-3.5 left-3.5 bg-[var(--bg-secondary)] rounded-lg px-3 py-1.5 text-xs font-semibold text-industrial shadow-sm">
                  {SAMPLE_PROPERTIES.length} properties in view
                </div>
              </div>
              <div className="flex flex-col gap-2.5 overflow-auto max-h-[540px]">
                {SAMPLE_PROPERTIES.map((p) => (
                  <PropertyCard key={p.id} p={p} compact onClick={handleCardClick} />
                ))}
              </div>
            </div>
          ) : view === 'list' ? (
            <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl overflow-hidden">
              <div className="hidden md:grid grid-cols-[80px_2fr_1fr_0.8fr_0.8fr_0.8fr_80px] px-5 py-3 text-[11px] font-semibold text-industrial-secondary tracking-[0.08em] uppercase border-b border-[var(--border-subtle)] bg-[var(--bg-cream,var(--bg-tertiary))]">
                <span />
                <span>Property</span>
                <span>Location</span>
                <span>Price</span>
                <span>Cap</span>
                <span>Score</span>
                <span />
              </div>
              {SAMPLE_PROPERTIES.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={handleCardClick}
                  className="grid grid-cols-[80px_2fr_1fr_0.8fr_0.8fr_0.8fr_80px] items-center px-5 py-3.5 border-b border-[var(--border-subtle)] last:border-b-0 hover:bg-[var(--bg-cream,var(--bg-tertiary))] transition-colors w-full text-left"
                >
                  <div
                    className="w-14 h-10 rounded-lg relative overflow-hidden"
                    style={{ background: p.grad }}
                  >
                    <div
                      className="absolute inset-0"
                      style={{
                        backgroundImage:
                          'repeating-linear-gradient(45deg, rgba(255,255,255,0.12) 0 4px, transparent 4px 8px)',
                      }}
                    />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-industrial">{p.addr}</div>
                    <div className="text-[11px] text-industrial-secondary mt-0.5">
                      {p.units} units · Built {p.year}
                    </div>
                  </div>
                  <div className="text-[13px] text-industrial-secondary">{p.city}</div>
                  <div className="font-display text-sm font-semibold text-industrial">{p.price}</div>
                  <div className="text-[13px] text-industrial-secondary">{p.cap}</div>
                  <div>
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${scorePillClass(
                        p.score,
                      )}`}
                    >
                      {p.score}
                    </span>
                  </div>
                  <ArrowRight size={14} className="text-industrial-muted justify-self-end" />
                </button>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 pb-8">
              {SAMPLE_PROPERTIES.map((p) => (
                <PropertyCard key={p.id} p={p} onClick={handleCardClick} />
              ))}
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}

export default SearchPage;
