import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { DealStage } from '../types/deal';

export type ViewMode = 'kanban' | 'list' | 'calendar' | 'map';

interface DealFilters {
  stage?: DealStage;
  search?: string;
  isArchived: boolean;
}

interface PipelineStore {
  // UI State
  viewMode: ViewMode;
  selectedDealId: string | null;
  isDetailDrawerOpen: boolean;
  isDealFormOpen: boolean;
  editingDealId: string | null;

  // Filters
  filters: DealFilters;

  // Actions
  setViewMode: (mode: ViewMode) => void;
  selectDeal: (dealId: string | null) => void;
  openDetailDrawer: (dealId: string) => void;
  closeDetailDrawer: () => void;
  openDealForm: (dealId?: string) => void;
  closeDealForm: () => void;
  setFilters: (filters: Partial<DealFilters>) => void;
  clearFilters: () => void;
}

const defaultFilters: DealFilters = {
  stage: undefined,
  search: undefined,
  isArchived: false,
};

export const usePipelineStore = create<PipelineStore>()(
  persist(
    (set) => ({
      // Initial state
      viewMode: 'kanban',
      selectedDealId: null,
      isDetailDrawerOpen: false,
      isDealFormOpen: false,
      editingDealId: null,
      filters: defaultFilters,

      // Actions
      setViewMode: (mode) => set({ viewMode: mode }),

      selectDeal: (dealId) => set({ selectedDealId: dealId }),

      openDetailDrawer: (dealId) =>
        set({
          selectedDealId: dealId,
          isDetailDrawerOpen: true,
        }),

      closeDetailDrawer: () =>
        set({
          isDetailDrawerOpen: false,
        }),

      openDealForm: (dealId) =>
        set({
          isDealFormOpen: true,
          editingDealId: dealId || null,
        }),

      closeDealForm: () =>
        set({
          isDealFormOpen: false,
          editingDealId: null,
        }),

      setFilters: (newFilters) =>
        set((state) => ({
          filters: { ...state.filters, ...newFilters },
        })),

      clearFilters: () => set({ filters: defaultFilters }),
    }),
    {
      name: 'pipeline-storage',
      partialize: (state) => ({
        viewMode: state.viewMode,
        filters: state.filters,
      }),
    }
  )
);
