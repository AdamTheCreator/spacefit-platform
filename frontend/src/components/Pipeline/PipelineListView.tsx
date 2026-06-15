import type { Deal, DealStage } from '../../types/deal';
import { getStageConfig, formatCurrency } from '../../types/deal';
import { usePipelineStore } from '../../stores/pipelineStore';
import { DataTable, type Column } from '../ui/DataTable';

interface PipelineListViewProps {
  deals: Deal[];
}

const STAGE_ORDER: Record<DealStage, number> = {
  intake: 0, qualification: 1, due_diligence: 2, tenant_vetting: 3,
  loi: 4, under_contract: 5, closed: 6, passed: 7, dead: 8,
};

function scoreColor(score: number): string {
  return score >= 60
    ? 'text-[var(--color-success)]'
    : score >= 30
      ? 'text-[var(--color-warning)]'
      : 'text-[var(--color-error)]';
}

function probColor(p: number): string {
  return p >= 75
    ? 'text-[var(--color-success)]'
    : p >= 50
      ? 'text-[var(--color-warning)]'
      : p >= 25
        ? 'text-[var(--accent)]'
        : 'text-[var(--color-error)]';
}

export function PipelineListView({ deals }: PipelineListViewProps) {
  const { openDetailDrawer } = usePipelineStore();

  const columns: Column<Deal>[] = [
    {
      key: 'name', header: 'Deal',
      sortValue: (d) => d.name.toLowerCase(),
      render: (d) => (
        <div>
          <div className="text-sm font-medium text-[var(--text-primary)]">{d.name}</div>
          {d.customer_name && (
            <div className="text-xs text-[var(--text-secondary)]">{d.customer_name}</div>
          )}
        </div>
      ),
    },
    {
      key: 'stage', header: 'Stage', width: 150,
      sortValue: (d) => STAGE_ORDER[d.stage] ?? 99,
      render: (d) => {
        const sc = getStageConfig(d.stage);
        return (
          <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${sc.color} bg-opacity-20 text-[var(--text-primary)]`}>
            <span className={`w-1.5 h-1.5 rounded-full ${sc.color}`} />
            {sc.label}
          </span>
        );
      },
    },
    {
      key: 'score', header: 'Score', width: 90, align: 'right',
      sortValue: (d) => d.property?.qualification_score ?? null,
      render: (d) => {
        const s = d.property?.qualification_score;
        return s != null ? (
          <span className={`text-sm font-mono font-medium ${scoreColor(s)}`}>{s}</span>
        ) : (
          <span className="text-xs text-[var(--text-secondary)]">--</span>
        );
      },
    },
    {
      key: 'probability', header: 'Probability', width: 120, align: 'right',
      sortValue: (d) => d.probability ?? 0,
      render: (d) => <span className={`text-sm ${probColor(d.probability)}`}>{d.probability}%</span>,
    },
    {
      key: 'commission', header: 'Commission', width: 130, align: 'right',
      sortValue: (d) => d.commission_amount ?? 0,
      render: (d) => (
        <span className="text-sm text-[var(--text-primary)] font-mono">
          {formatCurrency(d.commission_amount)}
        </span>
      ),
    },
    {
      key: 'close', header: 'Close Date', width: 120,
      sortValue: (d) => d.expected_close_date ?? null,
      render: (d) => <span className="text-sm text-[var(--text-secondary)]">{d.expected_close_date || '--'}</span>,
    },
    {
      key: 'property', header: 'Property', width: 220,
      render: (d) =>
        d.property ? (
          <div className="text-xs text-[var(--text-secondary)] max-w-[200px] truncate">
            {d.property.address}, {d.property.city}
          </div>
        ) : (
          <span className="text-xs text-[var(--text-secondary)]">--</span>
        ),
    },
  ];

  return (
    <DataTable
      columns={columns}
      rows={deals}
      rowKey={(d) => d.id}
      onRowClick={(d) => openDetailDrawer(d.id)}
      initialSort={{ key: 'stage', dir: 'asc' }}
      empty="No deals found"
    />
  );
}
