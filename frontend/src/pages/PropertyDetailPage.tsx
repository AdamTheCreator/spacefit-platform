import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { MapPin, Share2 } from 'lucide-react';
import { AppLayout } from '../components/Layout/AppLayout';
import { LineChart } from '../components/Dashboard/MiniCharts';

type Tab = 'overview' | 'financials' | 'timeline' | 'documents' | 'comps';

const TABS: Tab[] = ['overview', 'financials', 'timeline', 'documents', 'comps'];

const STATS: Array<[string, string]> = [
  ['Units', '124'],
  ['Built', '1998'],
  ['Sqft', '104,320'],
  ['Occupancy', '94%'],
  ['Rent/unit', '$1,612'],
  ['Parking', '182 spots'],
  ['Zoning', 'MF-3'],
  ['Lot', '6.4 ac'],
];

const TIMELINE: Array<[string, string, string]> = [
  ['Today', 'Market comp update', 'Cypress Park traded at 6.1% cap — 20 bps tighter'],
  ['2d ago', 'Underwriting note', 'Nia added sensitivity: rent +3% / exit cap 6.5%'],
  ['5d ago', 'Property added', 'Sourced from Acquisitions feed · thesis score 92'],
];

const COMPS: Array<[string, string, string]> = [
  ['Cedar Pines', '$26.1M', '6.1%'],
  ['Riverway 88', '$21.4M', '6.9%'],
  ['Maple Ridge', '$27.8M', '5.8%'],
];

const TEAM = ['JL', 'SO', 'NC', 'DV'];

export function PropertyDetailPage() {
  const { propertyId } = useParams<{ propertyId?: string }>();
  const [tab, setTab] = useState<Tab>('overview');

  // Sample data keyed by id. Real app would fetch.
  void propertyId;
  const property = {
    name: 'Elm Grove Apartments',
    address: '2412 Elm Ridge Ln, Austin, TX 78704',
    score: 92,
    thesis: 'Core+',
    price: '$24.4M',
    perUnit: '$196.8k / unit · below submarket comp',
    capRate: '6.8%',
    noi: '$1.66M',
    dscr: '1.34',
  };

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        {/* Breadcrumb */}
        <div className="px-8 py-4 border-b border-[var(--border-subtle)] flex items-center gap-2 text-[13px] text-industrial-secondary">
          <Link to="/search" className="hover:text-industrial transition-colors">Search</Link>
          <span>/</span>
          <span className="text-industrial font-medium">{property.name}</span>
        </div>

        <div className="px-8 py-7 max-w-[1400px]">
          {/* Hero + price/thesis cards */}
          <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-5 mb-5">
            {/* Hero image */}
            <div
              className="aspect-[16/9] rounded-2xl relative overflow-hidden border border-[var(--border-subtle)]"
              style={{ background: 'linear-gradient(135deg,#A7C7F7,#3A5BA0)' }}
            >
              <div
                className="absolute inset-0 pointer-events-none"
                style={{
                  backgroundImage:
                    'repeating-linear-gradient(45deg, rgba(255,255,255,0.12) 0 10px, transparent 10px 20px)',
                }}
              />
              <div className="absolute inset-x-4 bottom-4 flex justify-between items-end gap-3 flex-wrap">
                <div className="text-white">
                  <span className="inline-flex items-center px-3 py-1 rounded-full bg-[var(--color-neutral-900)] text-white text-[11px] font-semibold mb-2.5">
                    Score {property.score} · {property.thesis} match
                  </span>
                  <h2 className="font-display text-2xl sm:text-[32px] font-semibold text-white tracking-tight">
                    {property.name}
                  </h2>
                  <div className="text-sm mt-1 text-white/85 inline-flex items-center gap-1.5">
                    <MapPin size={13} />
                    {property.address}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/20 text-white border border-white/30 text-[13px] font-medium hover:bg-white/30 transition-colors backdrop-blur-sm">
                    <Share2 size={13} />
                    Share
                  </button>
                  <button className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-[13px] font-semibold transition-colors">
                    Start underwrite
                  </button>
                </div>
              </div>
            </div>

            {/* Asking price card + thesis-note card */}
            <div className="grid grid-rows-2 gap-4">
              <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-5">
                <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-industrial-secondary">
                  Asking price
                </div>
                <div className="font-display font-bold text-[32px] text-industrial mt-1.5 leading-none">
                  {property.price}
                </div>
                <div className="text-[13px] text-[var(--color-success)] mt-1">{property.perUnit}</div>
                <div className="grid grid-cols-3 gap-2.5 mt-4 pt-4 border-t border-[var(--border-subtle)]">
                  {[
                    ['Cap rate', property.capRate],
                    ['NOI', property.noi],
                    ['DSCR', property.dscr],
                  ].map(([k, v]) => (
                    <div key={k}>
                      <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-industrial-secondary">
                        {k}
                      </div>
                      <div className="font-display font-semibold text-[15px] text-industrial mt-0.5">
                        {v}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Thesis note with Planner goose */}
              <div className="bg-[var(--bg-cream,var(--bg-tertiary))] border border-[var(--border-subtle)] rounded-xl p-5 flex gap-3 items-center">
                <img
                  src="/mascots/goose-engineer.webp"
                  alt=""
                  aria-hidden="true"
                  className="w-[76px] h-[76px] object-contain shrink-0 select-none"
                  draggable={false}
                />
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--color-orbit,#3A5BA0)]">
                    Thesis note
                  </div>
                  <p className="text-[13px] text-industrial-secondary mt-1.5 leading-[1.5]">
                    Strong rent-growth submarket. Vintage aligns with your 1990+ filter. Consider 5%
                    rent bump at year 2.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-0.5 border-b border-[var(--border-subtle)] mb-5 overflow-x-auto">
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-4.5 py-3 text-sm font-medium capitalize whitespace-nowrap transition-colors -mb-px ${
                  tab === t
                    ? 'text-industrial border-b-2 border-[var(--accent)]'
                    : 'text-industrial-secondary border-b-2 border-transparent hover:text-industrial'
                }`}
                style={{ padding: '12px 18px' }}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Overview */}
          {tab === 'overview' ? (
            <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-5 pb-8">
              <div className="grid gap-5">
                <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-6">
                  <h3 className="font-display text-base font-semibold text-industrial">
                    Property stats
                  </h3>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4">
                    {STATS.map(([k, v]) => (
                      <div key={k}>
                        <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-industrial-secondary">
                          {k}
                        </div>
                        <div className="font-display font-semibold text-base text-industrial mt-0.5">
                          {v}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-6">
                  <div className="flex justify-between items-center mb-3.5">
                    <h3 className="font-display text-base font-semibold text-industrial">
                      Rent roll trend
                    </h3>
                    <span className="inline-flex items-center px-2.5 py-1 rounded-full bg-[#E3F1E5] text-[#2F7A3B] text-[11px] font-semibold">
                      +8.2% YoY
                    </span>
                  </div>
                  <LineChart data={[100, 102, 104, 103, 106, 108, 110, 112, 114, 113, 116, 119, 122]} height={140} />
                </div>

                <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-6">
                  <h3 className="font-display text-base font-semibold text-industrial mb-3.5">
                    Activity timeline
                  </h3>
                  <div className="grid gap-3.5">
                    {TIMELINE.map(([when, title, body], i) => (
                      <div key={title} className="flex gap-3.5">
                        <div className="w-[60px] text-[11px] text-industrial-secondary text-right font-medium pt-1">
                          {when}
                        </div>
                        <div className="w-[10px] flex justify-center relative shrink-0">
                          <span
                            className={`w-2 h-2 rounded-full mt-1.5 z-10 border-2 border-[var(--bg-secondary)] ${
                              i === 0 ? 'bg-[var(--accent)]' : 'bg-[var(--color-mist,#A7C7F7)]'
                            }`}
                          />
                          {i < TIMELINE.length - 1 && (
                            <span className="absolute top-3.5 bottom-[-14px] w-px bg-[var(--border-subtle)]" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-semibold text-industrial">{title}</div>
                          <div className="text-[13px] text-industrial-secondary mt-0.5">{body}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Right column */}
              <div className="grid gap-4 content-start">
                <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-5">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--color-orbit,#3A5BA0)]">
                    Next action
                  </div>
                  <div className="font-display text-[15px] font-semibold text-industrial mt-2">
                    Finish underwriting model
                  </div>
                  <p className="text-[13px] text-industrial-secondary mt-1.5 leading-[1.5]">
                    Exit cap and rent assumptions still open. Due before Friday's IC.
                  </p>
                  <button className="mt-3.5 w-full inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-sm font-semibold transition-colors">
                    Continue underwrite
                  </button>
                </div>

                <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-5">
                  <h4 className="font-display text-sm font-semibold text-industrial mb-3">
                    Comparable sales
                  </h4>
                  {COMPS.map(([name, price, cap], i) => (
                    <div
                      key={name}
                      className={`flex justify-between py-2.5 text-[13px] ${
                        i < COMPS.length - 1 ? 'border-b border-[var(--border-subtle)]' : ''
                      }`}
                    >
                      <span className="text-industrial font-medium">{name}</span>
                      <span className="text-industrial-secondary">{price}</span>
                      <span className="text-industrial-secondary font-semibold">{cap}</span>
                    </div>
                  ))}
                </div>

                <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-5">
                  <h4 className="font-display text-sm font-semibold text-industrial mb-3">Team</h4>
                  <div className="flex">
                    {TEAM.map((a, i) => (
                      <div
                        key={a}
                        className="w-8 h-8 rounded-full bg-gradient-to-br from-[var(--color-orbit,#3A5BA0)] to-[var(--color-mist,#A7C7F7)] text-white text-[11px] font-display font-semibold flex items-center justify-center border-2 border-[var(--bg-secondary)]"
                        style={{ marginLeft: i === 0 ? 0 : -8 }}
                      >
                        {a}
                      </div>
                    ))}
                    <button
                      className="w-8 h-8 rounded-full border border-dashed border-[var(--border-strong)] bg-[var(--bg-secondary)] text-industrial-secondary hover:text-industrial transition-colors"
                      style={{ marginLeft: -8 }}
                    >
                      +
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            // Placeholder for the other tabs — not yet ported
            <div className="bg-[var(--bg-secondary)] border border-dashed border-[var(--border-strong)] rounded-xl p-12 text-center text-industrial-secondary">
              <p className="text-sm">
                The <span className="font-semibold text-industrial capitalize">{tab}</span> tab
                hasn't been ported yet. Check back soon.
              </p>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}

export default PropertyDetailPage;
