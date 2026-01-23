import { useCallback, memo } from 'react';
import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import type { Deal, DealStage } from '../../types/deal';
import { getStageConfig, formatCurrency } from '../../types/deal';
import { KanbanCard } from './KanbanCard';

interface KanbanColumnProps {
  stage: DealStage;
  deals: Deal[];
  totalCommission: number;
  onDealClick: (dealId: string) => void;
}

export const KanbanColumn = memo(function KanbanColumn({ stage, deals, totalCommission, onDealClick }: KanbanColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: stage });
  const stageConfig = getStageConfig(stage);

  const handleCardClick = useCallback((dealId: string) => {
    onDealClick(dealId);
  }, [onDealClick]);

  return (
    <div
      ref={setNodeRef}
      className={`flex flex-col w-72 flex-shrink-0 bg-[var(--bg-elevated)] border transition-colors
                  ${isOver ? 'border-[var(--accent)] bg-[var(--accent)]/5' : 'border-industrial'}`}
    >
      {/* Column Header */}
      <div className="p-3 border-b border-industrial">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 ${stageConfig.color}`} />
            <h3 className="font-mono text-xs font-semibold uppercase tracking-wide text-industrial">{stageConfig.label}</h3>
          </div>
          <span className="px-2 py-0.5 bg-[var(--bg-tertiary)] border border-industrial-subtle font-mono text-xs text-industrial-secondary">
            {deals.length}
          </span>
        </div>
        <p className="font-mono text-sm font-semibold text-[var(--accent)]">
          {formatCurrency(totalCommission)}
        </p>
      </div>

      {/* Cards Container */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2 min-h-[200px] scrollbar-industrial">
        <SortableContext
          items={deals.map(d => d.id)}
          strategy={verticalListSortingStrategy}
        >
          {deals.map((deal) => (
            <KanbanCard
              key={deal.id}
              deal={deal}
              onClick={() => handleCardClick(deal.id)}
            />
          ))}
        </SortableContext>

        {/* Empty state */}
        {deals.length === 0 && (
          <div className="flex items-center justify-center h-24 label-technical">
            No deals
          </div>
        )}
      </div>
    </div>
  );
});
