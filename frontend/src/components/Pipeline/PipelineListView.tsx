import { useMemo, useState } from 'react';
import { ArrowUpDown } from 'lucide-react';
import type { Deal, DealStage } from '../../types/deal';
import { getStageConfig, formatCurrency } from '../../types/deal';
import { usePipelineStore } from '../../stores/pipelineStore';

interface PipelineListViewProps {
  deals: Deal[];
}

type SortField = 'name' | 'stage' | 'probability' | 'commission_amount' | 'expected_close_date' | 'qualification_score';
type SortDirection = 'asc' | 'desc';

const STAGE_ORDER: Record<DealStage, number> = {
  intake: 0, qualification: 1, due_diligence: 2, tenant_vetting: 3,
  loi: 4, under_contract: 5, closed: 6, passed: 7, dead: 8,
};

export function PipelineListView({ deals }: PipelineListViewProps) {
  const { openDetailDrawer } = usePipelineStore();
  const [sortField, setSortField] = useState<SortField>('stage');
  const [sortDir, setSortDir] = useState<SortDirection>('asc');

  const sorted = useMemo(() => {
    return [...deals].sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case 'name':
          cmp = a.name.localeCompare(b.name);
          break;
        case 'stage':
          cmp = (STAGE_ORDER[a.stage] ?? 99) - (STAGE_ORDER[b.stage] ?? 99);
          break;
        case 'probability':
          cmp = (a.probability ?? 0) - (b.probability ?? 0);
          break;
        case 'commission_amount':
          cmp = (a.commission_amount ?? 0) - (b.commission_amount ?? 0);
          break;
        case 'expected_close_date':
          cmp = (a.expected_close_date ?? '').localeCompare(b.expected_close_date ?? '');
          break;
        case 'qualification_score':
          cmp = (a.property?.qualification_score ?? 0) - (b.property?.qualification_score ?? 0);
          break;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [deals, sortField, sortDir]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  };

  const SortHeader = ({ field, label }: { field: SortField; label: string }) => (
    <th
      className="px-4 py-3 text-left text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider cursor-pointer hover:text-[var(--text-primary)] select-none"
      onClick={() => toggleSort(field)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        <ArrowUpDown className={`w-3 h-3 ${sortField === field ? 'text-[var(--accent)]' : 'opacity-30'}`} />
      </span>
    </th>
  );

  return (
    <div className="bg-[var(--bg-elevated)] border border-[var(--border)] rounded-lg overflow-hidden">
      <table className="min-w-full divide-y divide-[var(--border)]">
        <thead className="bg-[var(--bg-secondary)]">
          <tr>
            <SortHeader field="name" label="Deal" />
            <SortHeader field="stage" label="Stage" />
            <SortHeader field="qualification_score" label="Score" />
            <SortHeader field="probability" label="Probability" />
            <SortHeader field="commission_amount" label="Commission" />
            <SortHeader field="expected_close_date" label="Close Date" />
            <th className="px-4 py-3 text-left text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">
              Property
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border)]">
          {sorted.map(deal => {
            const stageConfig = getStageConfig(deal.stage);
            const score = deal.property?.qualification_score;
            return (
              <tr
                key={deal.id}
                className="hover:bg-[var(--bg-secondary)] cursor-pointer transition-colors"
                onClick={() => openDetailDrawer(deal.id)}
              >
                <td className="px-4 py-3">
                  <div className="text-sm font-medium text-[var(--text-primary)]">{deal.name}</div>
                  {deal.customer_name && (
                    <div className="text-xs text-[var(--text-secondary)]">{deal.customer_name}</div>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${stageConfig.color} bg-opacity-20 text-[var(--text-primary)]`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${stageConfig.color}`} />
                    {stageConfig.label}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {score != null ? (
                    <span className={`text-sm font-mono font-medium ${
                      score >= 60 ? 'text-green-400' : score >= 30 ? 'text-yellow-400' : 'text-red-400'
                    }`}>
                      {score}
                    </span>
                  ) : (
                    <span className="text-xs text-[var(--text-secondary)]">--</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className={`text-sm ${
                    deal.probability >= 75 ? 'text-green-400' :
                    deal.probability >= 50 ? 'text-yellow-400' :
                    deal.probability >= 25 ? 'text-[var(--accent)]' : 'text-red-400'
                  }`}>
                    {deal.probability}%
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-primary)] font-mono">
                  {formatCurrency(deal.commission_amount)}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {deal.expected_close_date || '--'}
                </td>
                <td className="px-4 py-3">
                  {deal.property ? (
                    <div className="text-xs text-[var(--text-secondary)] max-w-[200px] truncate">
                      {deal.property.address}, {deal.property.city}
                    </div>
                  ) : (
                    <span className="text-xs text-[var(--text-secondary)]">--</span>
                  )}
                </td>
              </tr>
            );
          })}
          {sorted.length === 0 && (
            <tr>
              <td colSpan={7} className="px-4 py-12 text-center text-[var(--text-secondary)]">
                No deals found
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
