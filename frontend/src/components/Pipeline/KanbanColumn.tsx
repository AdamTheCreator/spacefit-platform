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
      className={`flex flex-col w-72 flex-shrink-0 bg-gray-850 rounded-xl border transition-colors
                  ${isOver ? 'border-indigo-500 bg-indigo-500/5' : 'border-gray-700'}`}
    >
      {/* Column Header */}
      <div className="p-3 border-b border-gray-700">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <span className={`w-3 h-3 rounded-full ${stageConfig.color}`} />
            <h3 className="font-semibold text-white">{stageConfig.label}</h3>
          </div>
          <span className="px-2 py-0.5 bg-gray-700 rounded text-xs text-gray-300">
            {deals.length}
          </span>
        </div>
        <p className="text-sm text-green-400">
          {formatCurrency(totalCommission)}
        </p>
      </div>

      {/* Cards Container */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2 min-h-[200px]">
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
          <div className="flex items-center justify-center h-24 text-gray-500 text-sm">
            No deals
          </div>
        )}
      </div>
    </div>
  );
});
