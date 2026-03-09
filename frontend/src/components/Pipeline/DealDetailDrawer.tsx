import { X, MapPin, Calendar, DollarSign, User, Clock, FileText } from 'lucide-react';
import type { DealDetail } from '../../types/deal';
import { getStageConfig, formatCurrency, formatPSF, DEAL_STAGES } from '../../types/deal';
import { QualificationScorecard } from './QualificationScorecard';
import { usePipelineStore } from '../../stores/pipelineStore';
import { useDeal, useUpdateDealStage } from '../../hooks/useDeals';

export function DealDetailDrawer() {
  const { selectedDealId, isDetailDrawerOpen, closeDetailDrawer } = usePipelineStore();
  const { data: deal, isLoading } = useDeal(selectedDealId ?? '');
  const updateStage = useUpdateDealStage();

  if (!isDetailDrawerOpen || !selectedDealId) return null;

  const handleStageChange = (newStage: string) => {
    if (deal && deal.stage !== newStage) {
      updateStage.mutate({ id: deal.id, data: { stage: newStage as DealDetail['stage'] } });
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-40"
        onClick={closeDetailDrawer}
      />

      {/* Drawer */}
      <div className="fixed right-0 top-0 bottom-0 w-full max-w-lg bg-[var(--bg-primary)] border-l border-[var(--border)] z-50 overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-[var(--bg-primary)] border-b border-[var(--border)] px-6 py-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[var(--text-primary)] truncate">
            {isLoading ? 'Loading...' : deal?.name ?? 'Deal Details'}
          </h2>
          <button
            onClick={closeDetailDrawer}
            className="p-1 rounded hover:bg-[var(--bg-secondary)] text-[var(--text-secondary)]"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {isLoading || !deal ? (
          <div className="p-6 text-center text-[var(--text-secondary)]">Loading deal details...</div>
        ) : (
          <div className="p-6 space-y-6">
            {/* Stage selector */}
            <div>
              <label className="block text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider mb-2">Stage</label>
              <div className="flex flex-wrap gap-1.5">
                {DEAL_STAGES.map(s => {
                  const active = deal.stage === s.value;
                  return (
                    <button
                      key={s.value}
                      onClick={() => handleStageChange(s.value)}
                      className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                        active
                          ? `${s.color} text-white`
                          : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                      }`}
                    >
                      {s.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Key metrics */}
            <div className="grid grid-cols-2 gap-4">
              <MetricCard icon={DollarSign} label="Commission" value={formatCurrency(deal.commission_amount)} />
              <MetricCard icon={Clock} label="Probability" value={`${deal.probability}%`} />
              <MetricCard icon={Calendar} label="Expected Close" value={deal.expected_close_date ?? '--'} />
              <MetricCard icon={User} label="Customer" value={deal.customer_name ?? '--'} />
            </div>

            {/* Property info */}
            {deal.property && (
              <div>
                <h3 className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider mb-3">Property</h3>
                <div className="bg-[var(--bg-secondary)] rounded-lg p-4 space-y-2">
                  <div className="flex items-start gap-2">
                    <MapPin className="w-4 h-4 text-[var(--text-secondary)] mt-0.5 shrink-0" />
                    <div>
                      <div className="text-sm text-[var(--text-primary)]">{deal.property.name}</div>
                      <div className="text-xs text-[var(--text-secondary)]">
                        {deal.property.address}, {deal.property.city}, {deal.property.state} {deal.property.zip_code}
                      </div>
                    </div>
                  </div>
                  {deal.property.total_sf && (
                    <div className="text-xs text-[var(--text-secondary)]">
                      {deal.property.total_sf.toLocaleString()} SF | {deal.property.property_type}
                    </div>
                  )}
                  {deal.property.asking_price && (
                    <div className="text-xs text-[var(--text-secondary)]">
                      Asking: {formatCurrency(deal.property.asking_price)}
                      {deal.property.cap_rate && ` | ${deal.property.cap_rate}% Cap`}
                      {deal.property.price_psf && ` | ${formatPSF(deal.property.price_psf)}`}
                    </div>
                  )}
                  {deal.property.broker_name && (
                    <div className="text-xs text-[var(--text-secondary)]">
                      Broker: {deal.property.broker_name}
                      {deal.property.broker_company && ` (${deal.property.broker_company})`}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Qualification scorecard */}
            {deal.property && (
              <div>
                <h3 className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider mb-3">Qualification</h3>
                <QualificationScorecard property={deal.property} />
              </div>
            )}

            {/* Financial details */}
            <div>
              <h3 className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider mb-3">Financials</h3>
              <div className="bg-[var(--bg-secondary)] rounded-lg p-4 space-y-2 text-sm">
                <Row label="Asking Rent" value={formatPSF(deal.asking_rent_psf)} />
                <Row label="Negotiated Rent" value={formatPSF(deal.negotiated_rent_psf)} />
                <Row label="Square Footage" value={deal.square_footage?.toLocaleString() ?? '--'} />
                <Row label="Commission Rate" value={deal.commission_rate ? `${deal.commission_rate}%` : '--'} />
                <Row label="Lease Term" value={deal.lease_term_months ? `${deal.lease_term_months} months` : '--'} />
              </div>
            </div>

            {/* Stage history */}
            {deal.stage_history && deal.stage_history.length > 0 && (
              <div>
                <h3 className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider mb-3">Stage History</h3>
                <div className="space-y-2">
                  {deal.stage_history.map(h => {
                    const toConfig = getStageConfig(h.to_stage);
                    return (
                      <div key={h.id} className="flex items-center gap-3 text-xs">
                        <span className={`w-2 h-2 rounded-full ${toConfig.color} shrink-0`} />
                        <span className="text-[var(--text-secondary)]">
                          {h.from_stage ? `${getStageConfig(h.from_stage).label} → ` : ''}
                          {toConfig.label}
                        </span>
                        <span className="text-[var(--text-secondary)] ml-auto">
                          {new Date(h.changed_at).toLocaleDateString()}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Activities */}
            {deal.activities && deal.activities.length > 0 && (
              <div>
                <h3 className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider mb-3">
                  Activities ({deal.activities.length})
                </h3>
                <div className="space-y-2">
                  {deal.activities.slice(0, 10).map(a => (
                    <div key={a.id} className="bg-[var(--bg-secondary)] rounded-lg p-3">
                      <div className="flex items-center gap-2 mb-1">
                        <FileText className="w-3 h-3 text-[var(--text-secondary)]" />
                        <span className="text-sm text-[var(--text-primary)]">{a.title}</span>
                        <span className="text-xs text-[var(--text-secondary)] ml-auto">
                          {new Date(a.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      {a.description && (
                        <p className="text-xs text-[var(--text-secondary)] ml-5">{a.description}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Notes */}
            {deal.notes && (
              <div>
                <h3 className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider mb-3">Notes</h3>
                <p className="text-sm text-[var(--text-secondary)] bg-[var(--bg-secondary)] rounded-lg p-4">
                  {deal.notes}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}

function MetricCard({ icon: Icon, label, value }: { icon: typeof DollarSign; label: string; value: string }) {
  return (
    <div className="bg-[var(--bg-secondary)] rounded-lg p-3">
      <div className="flex items-center gap-1.5 mb-1">
        <Icon className="w-3 h-3 text-[var(--text-secondary)]" />
        <span className="text-xs text-[var(--text-secondary)]">{label}</span>
      </div>
      <div className="text-sm font-medium text-[var(--text-primary)]">{value}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-[var(--text-secondary)]">{label}</span>
      <span className="text-[var(--text-primary)] font-mono">{value}</span>
    </div>
  );
}
