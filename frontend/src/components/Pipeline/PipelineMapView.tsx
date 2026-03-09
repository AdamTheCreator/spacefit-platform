import { useMemo } from 'react';
import { MapPin } from 'lucide-react';
import type { Deal } from '../../types/deal';
import { getStageConfig, formatCurrency } from '../../types/deal';
import { usePipelineStore } from '../../stores/pipelineStore';

interface PipelineMapViewProps {
  deals: Deal[];
}

export function PipelineMapView({ deals }: PipelineMapViewProps) {
  const { openDetailDrawer } = usePipelineStore();

  const dealsWithLocation = useMemo(
    () => deals.filter(d => d.property?.latitude && d.property?.longitude),
    [deals]
  );

  const dealsWithoutLocation = useMemo(
    () => deals.filter(d => !d.property?.latitude || !d.property?.longitude),
    [deals]
  );

  // Group by state for a summary view until a real map library is added
  const byState = useMemo(() => {
    const map = new Map<string, Deal[]>();
    for (const deal of deals) {
      const state = deal.property?.state || 'Unknown';
      const list = map.get(state) || [];
      list.push(deal);
      map.set(state, list);
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [deals]);

  return (
    <div className="h-full overflow-y-auto space-y-6">
      {/* Map placeholder */}
      <div className="bg-[var(--bg-elevated)] border border-[var(--border)] rounded-lg p-8 text-center">
        <MapPin className="w-10 h-10 text-[var(--text-secondary)] mx-auto mb-3" />
        <h3 className="text-sm font-medium text-[var(--text-primary)] mb-1">Map View</h3>
        <p className="text-xs text-[var(--text-secondary)] mb-4">
          Interactive map coming soon. {dealsWithLocation.length} of {deals.length} deals have coordinates.
        </p>
      </div>

      {/* State-grouped property list */}
      {byState.map(([state, stateDeals]) => {
        const totalCommission = stateDeals.reduce((sum, d) => sum + (d.commission_amount || 0), 0);
        return (
          <div key={state}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">
                {state} ({stateDeals.length})
              </h3>
              <span className="text-xs text-[var(--accent)] font-mono">{formatCurrency(totalCommission)}</span>
            </div>
            <div className="bg-[var(--bg-elevated)] border border-[var(--border)] rounded-lg divide-y divide-[var(--border)]">
              {stateDeals.map(deal => {
                const stageConfig = getStageConfig(deal.stage);
                return (
                  <div
                    key={deal.id}
                    className="px-4 py-3 hover:bg-[var(--bg-secondary)] cursor-pointer transition-colors flex items-center gap-4"
                    onClick={() => openDetailDrawer(deal.id)}
                  >
                    <MapPin className="w-4 h-4 text-[var(--text-secondary)] shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-[var(--text-primary)] truncate">{deal.name}</div>
                      {deal.property && (
                        <div className="text-xs text-[var(--text-secondary)] truncate">
                          {deal.property.address}, {deal.property.city}
                        </div>
                      )}
                    </div>
                    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${stageConfig.color}`} />
                      <span className="text-[var(--text-secondary)]">{stageConfig.label}</span>
                    </span>
                    <span className="text-sm font-mono text-[var(--text-primary)] tabular-nums">
                      {formatCurrency(deal.commission_amount)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      {deals.length === 0 && (
        <div className="text-center py-12 text-[var(--text-secondary)]">
          No deals found
        </div>
      )}
    </div>
  );
}
