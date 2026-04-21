import { AppLayout } from '../components/Layout/AppLayout';

type InsightTone = 'orange' | 'gold' | 'navy';
type Mascot = 'mechanic' | 'welder' | 'engineer';

interface InsightCard {
  eyebrow: string;
  title: string;
  body: string;
  tone: InsightTone;
  mascot: Mascot;
}

const INSIGHTS: InsightCard[] = [
  {
    eyebrow: 'Market pulse',
    title: 'Austin cap rates tightened 20bps',
    body: 'Three comparable trades this week traded inside your thesis. Worth re-checking Elm Grove assumptions.',
    tone: 'orange',
    mascot: 'mechanic',
  },
  {
    eyebrow: 'Comp drift',
    title: 'Harper & Ninth looks 4% below market',
    body: 'Rent comps in Nashville 37206 moved up. Consider a 3% rent bump in your underwriting.',
    tone: 'gold',
    mascot: 'welder',
  },
  {
    eyebrow: 'Risk signal',
    title: 'Cypress Yards tax reassessment due',
    body: 'Hillsborough County reassesses in Q3. Model a +$48k/yr opex hit to stay on the safe side.',
    tone: 'navy',
    mascot: 'engineer',
  },
];

const MARKET_UPDATES: Array<[string, string, string]> = [
  ['Austin, TX',    'Permit activity up 12%. Two Class B complexes listed.',        'Just now'],
  ['Nashville, TN', 'Vacancy ticked down to 4.8% — tightest since 2019.',           '2h ago'],
  ['Tampa, FL',     'New flood map overlay affects 3 of your tracked parcels.',     '1d ago'],
  ['Raleigh, NC',   'Rent concessions dropped from 1.2mo to 0.4mo.',                '2d ago'],
];

function tonePillClass(tone: InsightTone): string {
  switch (tone) {
    case 'orange':
      return 'bg-[#FFE4CE] text-[#C25E1F]';
    case 'gold':
      return 'bg-[#FBEFC8] text-[#8A6417]';
    case 'navy':
      return 'bg-[var(--color-neutral-900)] text-white';
  }
}

export function InsightsPage() {
  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="px-8 py-6 grid gap-5 max-w-[1400px]">
          {/* 3 insight cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {INSIGHTS.map((c) => (
              <div
                key={c.title}
                className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl overflow-hidden flex flex-col"
              >
                <div className="bg-[var(--bg-cream,var(--bg-tertiary))] px-4 py-3.5 flex items-center gap-2.5 border-b border-[var(--border-subtle)]">
                  <img
                    src={`/mascots/goose-${c.mascot}.webp`}
                    alt=""
                    aria-hidden="true"
                    className="w-11 h-11 object-contain shrink-0 select-none"
                    draggable={false}
                  />
                  <span
                    className={`inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-semibold ${tonePillClass(
                      c.tone,
                    )}`}
                  >
                    {c.eyebrow}
                  </span>
                </div>
                <div className="p-5 flex flex-col flex-1">
                  <h3 className="font-display text-base font-semibold text-industrial">{c.title}</h3>
                  <p className="text-[13px] text-industrial-secondary mt-2 leading-[1.5]">{c.body}</p>
                  <button className="mt-auto pt-3.5 self-start inline-flex items-center gap-1 px-3.5 py-2 rounded-lg border border-[var(--border-strong)] text-sm font-medium text-industrial hover:bg-[var(--bg-tertiary)] transition-colors">
                    Investigate →
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Markets table */}
          <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-6 pb-2 mb-4">
            <h3 className="font-display text-base font-semibold text-industrial mb-3.5">
              This week in your markets
            </h3>
            <div className="grid gap-0">
              {MARKET_UPDATES.map(([market, update, when], i) => (
                <div
                  key={market}
                  className={`grid grid-cols-[120px_1fr_auto] sm:grid-cols-[160px_1fr_100px] gap-4 py-3.5 items-center ${
                    i < MARKET_UPDATES.length - 1 ? 'border-b border-[var(--border-subtle)]' : ''
                  }`}
                >
                  <span className="text-[13px] font-semibold text-industrial">{market}</span>
                  <span className="text-[13px] text-industrial-secondary">{update}</span>
                  <span className="text-xs text-industrial-muted text-right shrink-0">{when}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

export default InsightsPage;
