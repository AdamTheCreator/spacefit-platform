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
    ? 'bg-green-500'
    : deal.probability >= 50
    ? 'bg-amber-500'
    : deal.probability >= 25
    ? 'bg-orange-500'
    : 'bg-red-500';

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
      className={`bg-[var(--bg-tertiary)] border border-industrial-subtle p-4 cursor-pointer
                  hover:border-industrial hover:bg-[var(--bg-secondary)] transition-all
                  focus:outline-none focus:ring-2 focus:ring-[var(--accent)]
                  ${isDragging ? 'opacity-50 shadow-xl ring-2 ring-[var(--accent)]' : ''}`}
    >
      {/* Deal Name */}
      <h4 className="font-mono text-sm font-medium text-industrial mb-3 line-clamp-2">
        {deal.name}
      </h4>

      {/* Customer */}
      {deal.customer_name && (
        <div className="flex items-center gap-2 mb-2">
          <span className="label-technical">Client</span>
          <span className="font-mono text-xs text-industrial-secondary truncate">
            {deal.customer_name}
          </span>
        </div>
      )}

      {/* Property */}
      {deal.property && (
        <div className="flex items-center gap-2 mb-3">
          <span className="label-technical">Property</span>
          <span className="font-mono text-xs text-industrial-muted truncate">
            {deal.property.name}
          </span>
        </div>
      )}

      {/* Metrics Row */}
      <div className="flex items-center justify-between pt-3 border-t border-industrial-subtle">
        {/* Commission */}
        <div>
          <span className="label-technical block mb-1">Commission</span>
          <span className="font-mono text-sm font-semibold text-[var(--accent)]">
            {formatCurrency(deal.commission_amount)}
          </span>
        </div>

        {/* Probability */}
        <div className="text-right">
          <span className="label-technical block mb-1">Prob</span>
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 ${probabilityColor}`} />
            <span className="font-mono text-sm font-medium text-industrial">
              {deal.probability}%
            </span>
          </div>
        </div>
      </div>

      {/* Expected Close Date */}
      {deal.expected_close_date && (
        <div className="mt-3 pt-3 border-t border-industrial-subtle">
          <div className="flex items-center justify-between">
            <span className="label-technical">Expected Close</span>
            <span className="font-mono text-xs text-industrial-muted">
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
