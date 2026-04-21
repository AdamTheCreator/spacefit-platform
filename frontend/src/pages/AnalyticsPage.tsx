import { AppLayout } from '../components/Layout/AppLayout';
import { LineChart, BarChart } from '../components/Dashboard/MiniCharts';

function StatTile({
  label,
  value,
  delta,
  tone = 'up',
}: {
  label: string;
  value: string;
  delta?: string;
  tone?: 'up' | 'down' | 'flat';
}) {
  const deltaColor =
    tone === 'down' ? 'text-[var(--color-error)]'
    : tone === 'flat' ? 'text-industrial-secondary'
    : 'text-[var(--color-success)]';
  return (
    <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-industrial-secondary">
        {label}
      </div>
      <div className="font-display font-semibold text-[26px] text-industrial mt-1.5 leading-none tracking-tight">
        {value}
      </div>
      {delta && <div className={`text-xs mt-1.5 font-medium ${deltaColor}`}>{delta}</div>}
    </div>
  );
}

const BY_MARKET: Array<{ market: string; share: number; color: string }> = [
  { market: 'Austin, TX', share: 32, color: '#3A5BA0' },
  { market: 'Nashville', share: 24, color: '#FF8A3D' },
  { market: 'Tampa', share: 18, color: '#E5B85C' },
  { market: 'Raleigh', share: 14, color: '#A7C7F7' },
  { market: 'Atlanta', share: 12, color: '#1F3556' },
];

const TOP_ASSETS: Array<{ name: string; noi: string; cap: string; irr: string }> = [
  { name: 'Elm Grove Apartments', noi: '$1.66M', cap: '6.8%', irr: '16.2%' },
  { name: 'Harper & Ninth',       noi: '$1.21M', cap: '6.4%', irr: '15.8%' },
  { name: 'Riverbend Flats',      noi: '$0.94M', cap: '6.9%', irr: '15.1%' },
  { name: 'The Mercer',           noi: '$1.75M', cap: '5.9%', irr: '14.2%' },
  { name: 'Cypress Yards',        noi: '$2.31M', cap: '6.1%', irr: '13.9%' },
];

export function AnalyticsPage() {
  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="px-8 py-6 grid gap-5 max-w-[1400px]">
          {/* Navy header strip */}
          <div className="relative bg-[var(--color-neutral-900)] text-white rounded-2xl px-7 py-5 flex items-center gap-5 overflow-hidden flex-wrap">
            <div className="absolute w-1 h-1 rounded-full bg-[#A7C7F7] opacity-70" style={{ top: 14, left: 40 }} />
            <div className="absolute w-1 h-1 rounded-full bg-[#E5B85C] opacity-80" style={{ top: 50, left: 110 }} />
            <div className="absolute w-[3px] h-[3px] rounded-full bg-[#A7C7F7] opacity-60" style={{ top: 30, right: 200 }} />
            <div className="absolute w-1 h-1 rounded-full bg-[#E5B85C] opacity-60" style={{ top: 62, right: 80 }} />

            <div className="flex-1 relative min-w-0">
              <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#E5B85C]">
                Insights engine
              </div>
              <h2 className="font-display text-[22px] text-white mt-1 tracking-tight">
                Portfolio altitude · Q2 2026
              </h2>
            </div>
            <div className="flex gap-2 relative">
              <span className="inline-flex items-center px-3 py-1 rounded-full bg-white/10 border border-white/20 text-[11px] font-medium text-white">
                24 properties
              </span>
              <span className="inline-flex items-center px-3 py-1 rounded-full bg-white/10 border border-white/20 text-[11px] font-medium text-white">
                5 markets
              </span>
            </div>
          </div>

          {/* 5 KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3.5">
            <StatTile label="Portfolio NOI"    value="$4.2M"  delta="+6.8% QoQ" />
            <StatTile label="Weighted cap"     value="5.7%"   delta="+0.4pt" />
            <StatTile label="Occupancy"        value="93%"    delta="−1.1pt" tone="down" />
            <StatTile label="Avg rent growth"  value="4.2%"   delta="+0.6pt" />
            <StatTile label="IRR (trailing)"   value="14.8%"  delta="+1.2pt" />
          </div>

          {/* NOI & occupancy chart + By market */}
          <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-5">
            <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-6">
              <div className="flex justify-between items-center mb-4 flex-wrap gap-3">
                <div>
                  <h3 className="font-display text-base font-semibold text-industrial">NOI &amp; occupancy</h3>
                  <div className="text-xs text-industrial-secondary mt-0.5">
                    Rolling 18 months · portfolio-wide
                  </div>
                </div>
                <div className="flex gap-3 text-xs">
                  <span className="flex items-center gap-1.5 text-industrial-secondary">
                    <span className="w-2.5 h-2.5 rounded-sm bg-[var(--color-orbit,#3A5BA0)]" />
                    NOI
                  </span>
                  <span className="flex items-center gap-1.5 text-industrial-secondary">
                    <span className="w-2.5 h-2.5 rounded-sm bg-[var(--accent)]" />
                    Occupancy
                  </span>
                </div>
              </div>
              <LineChart
                data={[70, 72, 74, 73, 76, 78, 80, 82, 84, 83, 86, 88, 90, 92, 91, 94, 96, 98]}
                height={220}
              />
            </div>

            <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-6">
              <h3 className="font-display text-base font-semibold text-industrial mb-3.5">By market</h3>
              {BY_MARKET.map((m) => (
                <div key={m.market} className="mb-3 last:mb-0">
                  <div className="flex justify-between text-[13px] mb-1">
                    <span className="text-industrial font-medium">{m.market}</span>
                    <span className="text-industrial-secondary">{m.share}%</span>
                  </div>
                  <div className="bg-[var(--bg-tertiary)] h-2 rounded overflow-hidden">
                    <div
                      className="h-full rounded"
                      style={{ width: `${m.share * 2.6}%`, background: m.color }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Top performers + Expirations */}
          <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr] gap-5 pb-8">
            <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl overflow-hidden">
              <div className="flex justify-between items-center px-6 py-4 border-b border-[var(--border-subtle)]">
                <h3 className="font-display text-[15px] font-semibold text-industrial">
                  Top performing assets
                </h3>
                <button className="text-xs font-medium text-industrial-secondary hover:text-industrial transition-colors">
                  Export CSV
                </button>
              </div>
              <div className="grid grid-cols-[2fr_1fr_1fr_1fr] px-6 py-2.5 text-[11px] font-semibold uppercase tracking-[0.06em] text-industrial-secondary bg-[var(--bg-cream,var(--bg-tertiary))]">
                <span>Property</span>
                <span>NOI</span>
                <span>Cap</span>
                <span>IRR</span>
              </div>
              {TOP_ASSETS.map((a, i) => (
                <div
                  key={a.name}
                  className={`grid grid-cols-[2fr_1fr_1fr_1fr] items-center px-6 py-3.5 text-[13px] ${
                    i < TOP_ASSETS.length - 1 ? 'border-b border-[var(--border-subtle)]' : ''
                  }`}
                >
                  <span className="text-industrial font-medium">{a.name}</span>
                  <span className="font-display font-medium text-industrial-secondary">{a.noi}</span>
                  <span className="text-industrial-secondary">{a.cap}</span>
                  <span className="font-display font-semibold text-[var(--color-success)]">{a.irr}</span>
                </div>
              ))}
            </div>

            <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-6">
              <h3 className="font-display text-[15px] font-semibold text-industrial mb-3.5">
                Expirations next 90d
              </h3>
              <BarChart data={[3, 6, 4, 8, 12, 7, 5, 9, 14, 11, 6, 4]} height={140} />
              <div className="flex justify-between text-[11px] text-industrial-secondary mt-2.5">
                <span>May</span>
                <span>Jun</span>
                <span>Jul</span>
              </div>
              <div
                className="mt-4 p-3.5 bg-[var(--bg-cream,var(--bg-tertiary))] rounded-lg text-[13px] text-industrial-secondary leading-[1.5]"
              >
                <b className="text-industrial">89 leases</b> expire in the next 90 days. Early
                renewal campaigns ready for 62 of them.
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

export default AnalyticsPage;
