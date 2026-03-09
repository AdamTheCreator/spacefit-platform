import { Plus, LayoutGrid, List, Calendar, Map, Filter, Search } from 'lucide-react';
import { useDeals, usePipelineSummary } from '../hooks/useDeals';
import { usePipelineStore, type ViewMode } from '../stores/pipelineStore';
import { KanbanBoard, PipelineListView, PipelineMapView, PipelineCalendarView, DealDetailDrawer } from '../components/Pipeline';
import { formatCurrency } from '../types/deal';
import { AppLayout } from '../components/Layout';

const VIEW_OPTIONS: { value: ViewMode; label: string; icon: React.ReactNode }[] = [
  { value: 'kanban', label: 'Kanban', icon: <LayoutGrid className="w-4 h-4" /> },
  { value: 'list', label: 'List', icon: <List className="w-4 h-4" /> },
  { value: 'calendar', label: 'Calendar', icon: <Calendar className="w-4 h-4" /> },
  { value: 'map', label: 'Map', icon: <Map className="w-4 h-4" /> },
];

export function PipelinePage() {
  const { viewMode, setViewMode, filters, setFilters, openDealForm } = usePipelineStore();
  const { data: dealsData, isLoading: dealsLoading } = useDeals({
    stage: filters.stage,
    search: filters.search,
    isArchived: filters.isArchived,
    pageSize: 100, // Load all for kanban
  });
  const { data: pipelineSummary } = usePipelineSummary();

  const deals = dealsData?.items || [];

  return (
    <AppLayout>
      <div className="h-full flex flex-col bg-industrial">
        {/* Header */}
        <div className="flex-shrink-0 px-6 py-4 border-b border-industrial bg-[var(--bg-elevated)]">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="font-mono text-lg font-bold tracking-tight text-industrial">Deal Pipeline</h1>
              <p className="font-mono text-xs text-industrial-muted">
                <span className="data-value">{pipelineSummary?.total_deals || 0}</span> active deals
                {' '}&bull;{' '}
                <span className="text-[var(--accent)]">
                  {formatCurrency(pipelineSummary?.total_potential_commission || 0)} potential
                </span>
              </p>
            </div>

            <button
              onClick={() => openDealForm()}
              className="btn-industrial-primary"
            >
              <Plus className="w-4 h-4" />
              New Deal
            </button>
          </div>

          {/* Toolbar */}
          <div className="flex items-center justify-between">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-industrial-muted" />
              <input
                type="text"
                placeholder="Search deals..."
                value={filters.search || ''}
                onChange={(e) => setFilters({ search: e.target.value || undefined })}
                className="input-industrial pl-10 w-64"
              />
            </div>

            <div className="flex items-center gap-3">
              {/* Filters */}
              <button className="btn-industrial">
                <Filter className="w-4 h-4" />
                Filters
              </button>

              {/* View Mode Toggle */}
              <div className="flex items-center border border-industrial p-0.5">
                {VIEW_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => setViewMode(option.value)}
                    className={`flex items-center gap-2 px-3 py-1.5 transition-colors font-mono text-xs uppercase tracking-wide ${
                      viewMode === option.value
                        ? 'bg-[var(--accent)] text-[var(--color-industrial-900)]'
                        : 'text-industrial-muted hover:text-industrial'
                    }`}
                    title={option.label}
                  >
                    {option.icon}
                    <span className="hidden sm:inline">{option.label}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden p-6">
          {dealsLoading ? (
            <div className="flex items-center justify-center h-full">
              <div className="flex items-center gap-3">
                <div className="relative w-5 h-5">
                  <div className="w-5 h-5 border border-industrial" />
                  <div className="absolute inset-0 border-t border-[var(--accent)] animate-spin" />
                </div>
                <span className="label-technical">Loading deals...</span>
              </div>
            </div>
          ) : viewMode === 'kanban' ? (
            <KanbanBoard deals={deals} />
          ) : viewMode === 'list' ? (
            <PipelineListView deals={deals} />
          ) : viewMode === 'calendar' ? (
            <PipelineCalendarView deals={deals} />
          ) : viewMode === 'map' ? (
            <PipelineMapView deals={deals} />
          ) : null}
        </div>

        <DealDetailDrawer />
      </div>
    </AppLayout>
  );
}
