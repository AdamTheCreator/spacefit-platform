import { Plus, LayoutGrid, List, Calendar, Map, Filter, Search } from 'lucide-react';
import { useDeals, usePipelineSummary } from '../hooks/useDeals';
import { usePipelineStore, type ViewMode } from '../stores/pipelineStore';
import { KanbanBoard } from '../components/Pipeline';
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
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="flex-shrink-0 px-6 py-4 border-b border-gray-800">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold text-white">Deal Pipeline</h1>
              <p className="text-sm text-gray-400">
                {pipelineSummary?.total_deals || 0} active deals
                {' '}&bull;{' '}
                <span className="text-green-400">
                  {formatCurrency(pipelineSummary?.total_potential_commission || 0)} potential
                </span>
              </p>
            </div>

            <button
              onClick={() => openDealForm()}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500
                         text-white rounded-lg transition-colors"
            >
              <Plus className="w-4 h-4" />
              New Deal
            </button>
          </div>

          {/* Toolbar */}
          <div className="flex items-center justify-between">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search deals..."
                value={filters.search || ''}
                onChange={(e) => setFilters({ search: e.target.value || undefined })}
                className="pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white
                           placeholder-gray-500 focus:outline-none focus:border-indigo-500 w-64"
              />
            </div>

            <div className="flex items-center gap-4">
              {/* Filters */}
              <button
                className="flex items-center gap-2 px-3 py-2 bg-gray-800 hover:bg-gray-700
                           border border-gray-700 rounded-lg text-gray-300 transition-colors"
              >
                <Filter className="w-4 h-4" />
                Filters
              </button>

              {/* View Mode Toggle */}
              <div className="flex items-center bg-gray-800 rounded-lg border border-gray-700 p-1">
                {VIEW_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => setViewMode(option.value)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded transition-colors ${
                      viewMode === option.value
                        ? 'bg-indigo-600 text-white'
                        : 'text-gray-400 hover:text-white'
                    }`}
                    title={option.label}
                  >
                    {option.icon}
                    <span className="hidden sm:inline text-sm">{option.label}</span>
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
              <div className="flex items-center gap-3 text-gray-400">
                <span className="w-5 h-5 border-2 border-gray-600 border-t-indigo-500 rounded-full animate-spin" />
                Loading deals...
              </div>
            </div>
          ) : viewMode === 'kanban' ? (
            <KanbanBoard deals={deals} />
          ) : viewMode === 'list' ? (
            <div className="text-gray-400 text-center py-12">
              List view coming soon...
            </div>
          ) : viewMode === 'calendar' ? (
            <div className="text-gray-400 text-center py-12">
              Calendar view coming soon...
            </div>
          ) : viewMode === 'map' ? (
            <div className="text-gray-400 text-center py-12">
              Map view coming soon...
            </div>
          ) : null}
        </div>

        {/* TODO: Add DealDetailDrawer and DealForm modals */}
      </div>
    </AppLayout>
  );
}
