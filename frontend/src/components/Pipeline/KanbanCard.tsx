import { memo } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { Deal } from '../../types/deal';
import { formatCurrency } from '../../types/deal';

interface KanbanCardProps {
  deal: Deal;
  onClick: () => void;
}

export const KanbanCard = memo(function KanbanCard({ deal, onClick }: KanbanCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: deal.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const probabilityColor = deal.probability >= 75
    ? 'bg-[var(--color-success)]'
    : deal.probability >= 50
    ? 'bg-[var(--color-warning)]'
    : deal.probability >= 25
    ? 'bg-[var(--accent)]'
    : 'bg-[var(--color-error)]';

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick();
        }
      }}
      role="button"
      tabIndex={0}
      aria-label={`Deal: ${deal.name}. ${deal.customer_name ? `Customer: ${deal.customer_name}.` : ''} Commission: ${formatCurrency(deal.commission_amount)}. Click to view details.`}
      className={`bg-[var(--bg-elevated)] border border-[var(--border-subtle)] rounded-xl p-4 cursor-pointer
                  hover:border-[var(--border-strong)] hover:shadow-md transition-all duration-200
                  focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:ring-offset-2
                  ${isDragging ? 'opacity-60 shadow-xl ring-2 ring-[var(--accent)] scale-105' : 'shadow-sm'}`}
    >
      {/* Deal Name */}
      <h4 className="text-sm font-medium text-industrial mb-3 line-clamp-2">
        {deal.name}
      </h4>

      {/* Customer */}
      {deal.customer_name && (
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[10px] font-medium text-industrial-muted uppercase tracking-wide">Client</span>
          <span className="text-xs text-industrial-secondary truncate">
            {deal.customer_name}
          </span>
        </div>
      )}

      {/* Property */}
      {deal.property && (
        <div className="flex items-center gap-2 mb-3">
          <span className="text-[10px] font-medium text-industrial-muted uppercase tracking-wide">Property</span>
          <span className="text-xs text-industrial-muted truncate">
            {deal.property.name}
          </span>
        </div>
      )}

      {/* Metrics Row */}
      <div className="flex items-center justify-between pt-3 border-t border-[var(--border-subtle)]">
        {/* Commission */}
        <div>
          <span className="text-[10px] font-medium text-industrial-muted uppercase tracking-wide block mb-1">Commission</span>
          <span className="text-sm font-semibold text-[var(--accent)] tabular-nums">
            {formatCurrency(deal.commission_amount)}
          </span>
        </div>

        {/* Probability */}
        <div className="text-right">
          <span className="text-[10px] font-medium text-industrial-muted uppercase tracking-wide block mb-1">Prob</span>
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${probabilityColor}`} />
            <span className="text-sm font-medium text-industrial tabular-nums">
              {deal.probability}%
            </span>
          </div>
        </div>
      </div>

      {/* Expected Close Date */}
      {deal.expected_close_date && (
        <div className="mt-3 pt-3 border-t border-[var(--border-subtle)]">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-medium text-industrial-muted uppercase tracking-wide">Expected Close</span>
            <span className="text-xs text-industrial-muted">
              {new Date(deal.expected_close_date).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: '2-digit'
              })}
            </span>
          </div>
        </div>
      )}
    </div>
  );
});
