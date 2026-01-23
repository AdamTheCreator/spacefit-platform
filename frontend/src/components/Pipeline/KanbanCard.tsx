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
      className={`bg-gray-800 border border-gray-700 rounded-lg p-3 cursor-pointer
                  hover:border-gray-600 hover:bg-gray-750 transition-all
                  focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-gray-900
                  ${isDragging ? 'opacity-50 shadow-lg ring-2 ring-indigo-500' : ''}`}
    >
      {/* Deal Name */}
      <h4 className="font-medium text-white text-sm mb-2 line-clamp-2">
        {deal.name}
      </h4>

      {/* Customer */}
      {deal.customer_name && (
        <p className="text-xs text-gray-400 mb-2 truncate">
          {deal.customer_name}
        </p>
      )}

      {/* Property */}
      {deal.property && (
        <p className="text-xs text-gray-500 mb-2 truncate">
          {deal.property.name}
        </p>
      )}

      {/* Metrics */}
      <div className="flex items-center justify-between text-xs">
        {/* Commission */}
        <span className="text-green-400 font-medium">
          {formatCurrency(deal.commission_amount)}
        </span>

        {/* Probability */}
        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
          deal.probability >= 75 ? 'bg-green-500/20 text-green-400' :
          deal.probability >= 50 ? 'bg-yellow-500/20 text-yellow-400' :
          deal.probability >= 25 ? 'bg-orange-500/20 text-orange-400' :
          'bg-red-500/20 text-red-400'
        }`}>
          {deal.probability}%
        </span>
      </div>

      {/* Expected Close Date */}
      {deal.expected_close_date && (
        <p className="text-xs text-gray-500 mt-2">
          Close: {new Date(deal.expected_close_date).toLocaleDateString()}
        </p>
      )}
    </div>
  );
});
