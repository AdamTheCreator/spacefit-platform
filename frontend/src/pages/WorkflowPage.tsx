import { Plus, Clock, SlidersHorizontal } from 'lucide-react';
import { AppLayout } from '../components/Layout/AppLayout';

interface Deal {
  title: string;
  city: string;
  price: string;
  assignee: string;
  score?: number;
  days?: number;
}

interface Column {
  stage: string;
  color: string;
  deals: Deal[];
}

const COLUMNS: Column[] = [
  {
    stage: 'Sourced',
    color: '#A7C7F7',
    deals: [
      { title: 'Peachtree Commons', city: 'Atlanta',    price: '$41.6M', assignee: 'SO' },
      { title: 'North Loop 88',     city: 'Minneapolis', price: '$22.1M', assignee: 'JL' },
      { title: 'Birchwood Trace',   city: 'Columbus',    price: '$17.8M', assignee: 'NC' },
    ],
  },
  {
    stage: 'Screening',
    color: '#3A5BA0',
    deals: [
      { title: 'The Mercer',    city: 'Raleigh', price: '$29.7M', assignee: 'JL', score: 81 },
      { title: 'Cypress Yards', city: 'Tampa',   price: '$38.0M', assignee: 'SO', score: 84 },
    ],
  },
  {
    stage: 'Underwriting',
    color: '#E5B85C',
    deals: [
      { title: 'Elm Grove Apartments', city: 'Austin',    price: '$24.4M', assignee: 'JL', score: 92, days: 3 },
      { title: 'Harper & Ninth',       city: 'Nashville', price: '$18.9M', assignee: 'NC', score: 88, days: 5 },
    ],
  },
  {
    stage: 'LOI',
    color: '#FF8A3D',
    deals: [
      { title: 'Riverbend Flats', city: 'Indianapolis', price: '$14.2M', assignee: 'DV' },
    ],
  },
  {
    stage: 'Closing',
    color: '#2F7A3B',
    deals: [
      { title: 'Oak & Vine', city: 'Charlotte', price: '$19.6M', assignee: 'SO' },
    ],
  },
];

function scorePillClass(score: number): string {
  return score >= 85
    ? 'bg-[#E3F1E5] text-[#2F7A3B]'
    : 'bg-[#FBEFC8] text-[#8A6417]';
}

function DealCard({ deal }: { deal: Deal }) {
  return (
    <div
      className="bg-[var(--bg-secondary)] rounded-[10px] p-3.5 border border-[var(--border-subtle)] cursor-grab hover:border-[var(--border-strong)] hover:shadow-sm transition-all"
      draggable
    >
      <div className="text-[13.5px] font-semibold text-industrial leading-tight">
        {deal.title}
      </div>
      <div className="text-[11px] text-industrial-secondary mt-0.5">{deal.city}</div>
      <div className="flex justify-between items-center mt-3">
        <span className="font-display text-[13px] font-bold text-industrial">{deal.price}</span>
        <div
          className="w-[22px] h-[22px] rounded-full bg-gradient-to-br from-[var(--color-orbit,#3A5BA0)] to-[var(--color-mist,#A7C7F7)] text-white font-display font-semibold text-[9px] flex items-center justify-center"
          title={`Assigned to ${deal.assignee}`}
        >
          {deal.assignee}
        </div>
      </div>
      {(deal.score !== undefined || deal.days !== undefined) && (
        <div className="flex gap-1.5 mt-2.5 pt-2.5 border-t border-[var(--border-subtle)]">
          {deal.score !== undefined && (
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${scorePillClass(
                deal.score,
              )}`}
            >
              Score {deal.score}
            </span>
          )}
          {deal.days !== undefined && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--bg-tertiary)] text-industrial-secondary text-[10px] font-medium">
              <Clock size={9} />
              {deal.days}d
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function ReadyForLiftoffSlot() {
  return (
    <div className="bg-[var(--bg-secondary)] rounded-[10px] p-4 border border-dashed border-[var(--border-strong)] text-center text-[12px] text-industrial-secondary flex flex-col items-center gap-2">
      <img
        src="/mascots/goose-launch.webp"
        alt=""
        aria-hidden="true"
        className="w-[60px] h-[60px] object-contain select-none"
        draggable={false}
      />
      <div className="font-medium text-industrial">Ready for liftoff</div>
      <div>Your next close lands here.</div>
    </div>
  );
}

export function WorkflowPage() {
  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="px-8 py-6 max-w-[1400px]">
          <div className="flex justify-between items-center mb-5 flex-wrap gap-3">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--color-orbit,#3A5BA0)]">
                Operations
              </div>
              <h2 className="font-display text-[22px] font-semibold text-industrial mt-1 tracking-tight">
                Acquisition pipeline
              </h2>
            </div>
            <div className="flex gap-2.5">
              <button className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg border border-[var(--border-strong)] text-sm font-medium text-industrial hover:bg-[var(--bg-tertiary)] transition-colors">
                <SlidersHorizontal size={14} />
                Filters
              </button>
              <button className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[var(--color-neutral-900)] text-white text-sm font-semibold hover:bg-[var(--color-neutral-800)] transition-colors shadow-sm">
                <Plus size={14} />
                Add deal
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
            {COLUMNS.map((col) => (
              <div
                key={col.stage}
                className="bg-[var(--bg-cream,var(--bg-tertiary))] rounded-[14px] p-3 min-h-[400px]"
              >
                <div className="flex items-center gap-2 px-1.5 pb-3 border-b border-[var(--border-subtle)]">
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ background: col.color }}
                  />
                  <span className="text-[13px] font-semibold text-industrial">{col.stage}</span>
                  <span className="ml-auto text-[11px] text-industrial-secondary bg-[var(--bg-secondary)] px-2 py-0.5 rounded-lg">
                    {col.deals.length}
                  </span>
                </div>
                <div className="grid gap-2.5 mt-3">
                  {col.deals.map((d, i) => (
                    <DealCard key={i} deal={d} />
                  ))}
                  {col.stage === 'Closing' && <ReadyForLiftoffSlot />}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

export default WorkflowPage;
