import { useState, useMemo } from 'react';
import {
  DndContext,
  DragOverlay,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
  type DragEndEvent,
} from '@dnd-kit/core';
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import type { Deal, DealStage } from '../../types/deal';
import { DEAL_STAGES } from '../../types/deal';
import { KanbanColumn } from './KanbanColumn';
import { KanbanCard } from './KanbanCard';
import { useUpdateDealStage } from '../../hooks/useDeals';
import { usePipelineStore } from '../../stores/pipelineStore';

const ALL_STAGES: DealStage[] = [
  'intake', 'qualification', 'due_diligence', 'tenant_vetting',
  'loi', 'under_contract', 'closed', 'passed', 'dead',
];

interface KanbanBoardProps {
  deals: Deal[];
}

export function KanbanBoard({ deals }: KanbanBoardProps) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const { openDetailDrawer } = usePipelineStore();
  const updateStageMutation = useUpdateDealStage();

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // Group deals by stage
  const dealsByStage = useMemo(() => {
    const grouped = {} as Record<DealStage, Deal[]>;
    for (const stage of ALL_STAGES) {
      grouped[stage] = [];
    }

    deals.forEach((deal) => {
      if (grouped[deal.stage]) {
        grouped[deal.stage].push(deal);
      }
    });

    return grouped;
  }, [deals]);

  // Calculate commission totals by stage
  const commissionByStage = useMemo(() => {
    const totals = {} as Record<DealStage, number>;
    for (const stage of ALL_STAGES) {
      totals[stage] = 0;
    }

    deals.forEach((deal) => {
      if (totals[deal.stage] !== undefined) {
        totals[deal.stage] += deal.commission_amount || 0;
      }
    });

    return totals;
  }, [deals]);

  const activeDeal = activeId ? deals.find((d) => d.id === activeId) : null;

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveId(null);

    if (!over) return;

    const dealId = active.id as string;
    const newStage = over.id as DealStage;

    // Find the deal
    const deal = deals.find((d) => d.id === dealId);
    if (!deal || deal.stage === newStage) return;

    // Update the stage
    updateStageMutation.mutate({
      id: dealId,
      data: { stage: newStage },
    });
  };

  const handleDealClick = (dealId: string) => {
    // Only open if not dragging
    if (!activeId) {
      openDetailDrawer(dealId);
    }
  };

  // Filter out terminal stages (passed, dead) from default view
  const visibleStages = DEAL_STAGES.filter(s => s.value !== 'passed' && s.value !== 'dead');

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="flex gap-4 overflow-x-auto pb-4 min-h-[calc(100vh-300px)]">
        {visibleStages.map((stage) => (
          <KanbanColumn
            key={stage.value}
            stage={stage.value}
            deals={dealsByStage[stage.value]}
            totalCommission={commissionByStage[stage.value]}
            onDealClick={handleDealClick}
          />
        ))}
      </div>

      <DragOverlay>
        {activeDeal ? (
          <div className="opacity-80">
            <KanbanCard deal={activeDeal} onClick={() => {}} />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
