import { useMemo, useState } from 'react';
import { Plus, X } from 'lucide-react';
import { AppLayout } from '../components/Layout/AppLayout';
import { useDeals, useUpdateDeal, useCreateDeal, usePipelineSummary } from '../hooks/useDeals';
import { DEAL_STAGES, formatCurrency, type Deal, type DealStage } from '../types/deal';

// Space Goose stage accent dots (legacy palette preserved). Closing/terminal
// stages trail the active funnel and read in a calmer tone.
const STAGE_DOT: Record<DealStage, string> = {
  intake: '#A7C7F7',
  qualification: '#3A5BA0',
  due_diligence: '#5B7FC4',
  tenant_vetting: '#8A6CC4',
  loi: '#E5B85C',
  under_contract: '#FF8A3D',
  closed: '#2F7A3B',
  passed: '#9AA3AF',
  dead: '#C4736B',
};

// Terminal columns are visually de-emphasised but remain reachable drop targets.
const TRAILING_STAGES: ReadonlySet<DealStage> = new Set(['passed', 'dead']);

function probabilityPillClass(probability: number): string {
  return probability >= 60
    ? 'bg-[#E3F1E5] text-[#2F7A3B]'
    : 'bg-[#FBEFC8] text-[#8A6417]';
}

function dealSubtitle(deal: Deal): string | null {
  if (deal.property?.name) {
    const loc = [deal.property.city, deal.property.state].filter(Boolean).join(', ');
    return loc ? `${deal.property.name} · ${loc}` : deal.property.name;
  }
  if (deal.customer_name) return deal.customer_name;
  return null;
}

function formatSf(sf: number | undefined | null): string | null {
  if (sf === undefined || sf === null) return null;
  return `${new Intl.NumberFormat('en-US').format(sf)} SF`;
}

function formatCloseDate(value: string | undefined): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function DealCard({
  deal,
  onDragStart,
  onDragEnd,
  isDragging,
}: {
  deal: Deal;
  onDragStart: (deal: Deal) => void;
  onDragEnd: () => void;
  isDragging: boolean;
}) {
  const subtitle = dealSubtitle(deal);
  const sf = formatSf(deal.square_footage);
  const closeDate = formatCloseDate(deal.expected_close_date);

  return (
    <div
      className={`bg-[var(--bg-secondary)] rounded-[10px] p-3.5 border border-[var(--border-subtle)] cursor-grab active:cursor-grabbing hover:border-[var(--border-strong)] hover:shadow-sm transition-all ${
        isDragging ? 'opacity-40' : ''
      }`}
      draggable
      onDragStart={() => onDragStart(deal)}
      onDragEnd={onDragEnd}
    >
      <div className="text-[13.5px] font-semibold text-industrial leading-tight">
        {deal.name}
      </div>
      {subtitle && (
        <div className="text-[11px] text-industrial-secondary mt-0.5 truncate">{subtitle}</div>
      )}
      <div className="flex justify-between items-center mt-3 gap-2">
        <span className="font-display text-[13px] font-bold text-industrial">
          {deal.commission_amount ? formatCurrency(deal.commission_amount) : '—'}
        </span>
        {sf && (
          <span className="font-mono text-[10.5px] text-industrial-secondary shrink-0">{sf}</span>
        )}
      </div>
      <div className="flex flex-wrap gap-1.5 mt-2.5 pt-2.5 border-t border-[var(--border-subtle)]">
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${probabilityPillClass(
            deal.probability,
          )}`}
        >
          {deal.probability}%
        </span>
        {closeDate && (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-[var(--bg-tertiary)] text-industrial-secondary text-[10px] font-medium">
            {closeDate}
          </span>
        )}
      </div>
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

function EmptyState({ onAddDeal }: { onAddDeal: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-20 gap-4">
      <img
        src="/mascots/goose-planet.webp"
        alt=""
        aria-hidden="true"
        className="w-[120px] h-[120px] object-contain select-none"
        draggable={false}
      />
      <div className="font-display text-[18px] font-semibold text-industrial">No deals in flight yet</div>
      <p className="text-[13px] text-industrial-secondary max-w-[360px]">
        Your acquisition pipeline is empty. Add your first deal and drag it across the stages as it
        progresses toward closing.
      </p>
      <button
        onClick={onAddDeal}
        className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--color-neutral-900)] text-white text-sm font-semibold hover:bg-[var(--color-neutral-800)] transition-colors shadow-sm"
      >
        <Plus size={15} />
        New deal
      </button>
    </div>
  );
}

function NewDealModal({
  onClose,
  onCreate,
  isPending,
}: {
  onClose: () => void;
  onCreate: (name: string, stage: DealStage) => void;
  isPending: boolean;
}) {
  const [name, setName] = useState('');
  const [stage, setStage] = useState<DealStage>('intake');

  const canSubmit = name.trim().length > 0 && !isPending;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-[420px] rounded-[14px] bg-[var(--bg-secondary)] border border-[var(--border-subtle)] shadow-xl p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display text-[16px] font-semibold text-industrial">New deal</h3>
          <button
            onClick={onClose}
            className="text-industrial-secondary hover:text-industrial transition-colors"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (canSubmit) onCreate(name.trim(), stage);
          }}
        >
          <label className="block text-[12px] font-medium text-industrial-secondary mb-1.5">
            Deal name
          </label>
          <input
            autoFocus
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Riverbend Flats"
            className="input-industrial w-full mb-4"
          />

          <label className="block text-[12px] font-medium text-industrial-secondary mb-1.5">
            Starting stage
          </label>
          <select
            value={stage}
            onChange={(e) => setStage(e.target.value as DealStage)}
            className="input-industrial w-full mb-5"
          >
            {DEAL_STAGES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>

          <div className="flex justify-end gap-2.5">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-2 rounded-lg border border-[var(--border-strong)] text-sm font-medium text-industrial hover:bg-[var(--bg-tertiary)] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!canSubmit}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[var(--color-neutral-900)] text-white text-sm font-semibold hover:bg-[var(--color-neutral-800)] transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Plus size={14} />
              {isPending ? 'Creating…' : 'Create deal'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function WorkflowPage() {
  const { data: dealsData, isLoading, isError } = useDeals({ pageSize: 100 });
  const { data: pipelineSummary } = usePipelineSummary();
  const updateDeal = useUpdateDeal();
  const createDeal = useCreateDeal();

  const [draggingDeal, setDraggingDeal] = useState<Deal | null>(null);
  const [dragOverStage, setDragOverStage] = useState<DealStage | null>(null);
  const [showNewDeal, setShowNewDeal] = useState(false);

  const deals = useMemo(
    () => (dealsData?.items ?? []).filter((d) => !d.is_archived),
    [dealsData],
  );

  const dealsByStage = useMemo(() => {
    const grouped = new Map<DealStage, Deal[]>();
    for (const s of DEAL_STAGES) grouped.set(s.value, []);
    for (const deal of deals) {
      const bucket = grouped.get(deal.stage);
      if (bucket) bucket.push(deal);
    }
    return grouped;
  }, [deals]);

  // Per-stage commission totals from the pipeline summary (falls back to 0).
  const commissionByStage = useMemo(() => {
    const map = new Map<DealStage, number>();
    for (const s of pipelineSummary?.stages ?? []) {
      map.set(s.stage, s.total_commission);
    }
    return map;
  }, [pipelineSummary]);

  const handleDrop = (targetStage: DealStage) => {
    const deal = draggingDeal;
    setDraggingDeal(null);
    setDragOverStage(null);
    if (!deal || deal.stage === targetStage) return;
    // Stage change is what moves the card; PUT /deals/{id} records history server-side.
    updateDeal.mutate({ id: deal.id, data: { stage: targetStage } });
  };

  const handleCreate = (name: string, stage: DealStage) => {
    createDeal.mutate(
      { name, stage },
      { onSuccess: () => setShowNewDeal(false) },
    );
  };

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
              {pipelineSummary && (
                <p className="text-[12px] text-industrial-secondary mt-1">
                  <span className="font-semibold text-industrial">{pipelineSummary.total_deals}</span>{' '}
                  active deals ·{' '}
                  <span className="text-[var(--accent)] font-semibold">
                    {formatCurrency(pipelineSummary.total_potential_commission)}
                  </span>{' '}
                  potential commission
                </p>
              )}
            </div>
            <div className="flex gap-2.5">
              <button
                onClick={() => setShowNewDeal(true)}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[var(--color-neutral-900)] text-white text-sm font-semibold hover:bg-[var(--color-neutral-800)] transition-colors shadow-sm"
              >
                <Plus size={14} />
                New deal
              </button>
            </div>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-20 text-[13px] text-industrial-secondary">
              Loading pipeline…
            </div>
          ) : isError && deals.length === 0 ? (
            <div className="flex flex-col items-center justify-center text-center py-20 gap-3">
              <img
                src="/mascots/goose-mechanic.webp"
                alt=""
                aria-hidden="true"
                className="w-[96px] h-[96px] object-contain select-none"
                draggable={false}
              />
              <div className="font-display text-[16px] font-semibold text-industrial">
                Couldn’t load your pipeline
              </div>
              <p className="text-[13px] text-industrial-secondary max-w-[340px]">
                Something went wrong fetching your deals. Try refreshing the page.
              </p>
            </div>
          ) : deals.length === 0 ? (
            <EmptyState onAddDeal={() => setShowNewDeal(true)} />
          ) : (
            <div className="flex gap-3.5 overflow-x-auto pb-3">
              {DEAL_STAGES.map((col) => {
                const stageDeals = dealsByStage.get(col.value) ?? [];
                const isTrailing = TRAILING_STAGES.has(col.value);
                const isDropTarget = dragOverStage === col.value;
                const commission = commissionByStage.get(col.value) ?? 0;
                return (
                  <div
                    key={col.value}
                    onDragOver={(e) => {
                      e.preventDefault();
                      if (dragOverStage !== col.value) setDragOverStage(col.value);
                    }}
                    onDragLeave={(e) => {
                      // Only clear when leaving the column, not when entering a child.
                      if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                        setDragOverStage((s) => (s === col.value ? null : s));
                      }
                    }}
                    onDrop={() => handleDrop(col.value)}
                    className={`shrink-0 w-[248px] bg-[var(--bg-cream,var(--bg-tertiary))] rounded-[14px] p-3 min-h-[400px] transition-all ${
                      isTrailing ? 'opacity-75' : ''
                    } ${
                      isDropTarget
                        ? 'ring-2 ring-[var(--accent)] ring-offset-1 ring-offset-[var(--bg-primary)]'
                        : ''
                    }`}
                  >
                    <div className="flex items-center gap-2 px-1.5 pb-3 border-b border-[var(--border-subtle)]">
                      <span
                        className="w-2 h-2 rounded-full shrink-0"
                        style={{ background: STAGE_DOT[col.value] }}
                      />
                      <span className="text-[13px] font-semibold text-industrial">{col.label}</span>
                      <span className="ml-auto text-[11px] text-industrial-secondary bg-[var(--bg-secondary)] px-2 py-0.5 rounded-lg">
                        {stageDeals.length}
                      </span>
                    </div>
                    {commission > 0 && (
                      <div className="px-1.5 pt-2 font-mono text-[10.5px] text-industrial-secondary">
                        {formatCurrency(commission)}
                      </div>
                    )}
                    <div className="grid gap-2.5 mt-3">
                      {stageDeals.map((deal) => (
                        <DealCard
                          key={deal.id}
                          deal={deal}
                          isDragging={draggingDeal?.id === deal.id}
                          onDragStart={setDraggingDeal}
                          onDragEnd={() => {
                            setDraggingDeal(null);
                            setDragOverStage(null);
                          }}
                        />
                      ))}
                      {col.value === 'closed' && stageDeals.length === 0 && <ReadyForLiftoffSlot />}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {showNewDeal && (
        <NewDealModal
          onClose={() => setShowNewDeal(false)}
          onCreate={handleCreate}
          isPending={createDeal.isPending}
        />
      )}
    </AppLayout>
  );
}

export default WorkflowPage;
