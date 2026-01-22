import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/axios';
import type {
  Deal,
  DealDetail,
  DealCreate,
  DealUpdate,
  DealStageUpdate,
  DealListResponse,
  DealActivityCreate,
  DealActivity,
  PipelineSummary,
  CommissionForecast,
  DealCalendarItem,
  DealStage,
} from '../types/deal';

interface DealsQueryParams {
  page?: number;
  pageSize?: number;
  stage?: DealStage;
  search?: string;
  isArchived?: boolean;
}

// Query keys
export const dealKeys = {
  all: ['deals'] as const,
  lists: () => [...dealKeys.all, 'list'] as const,
  list: (params: DealsQueryParams) => [...dealKeys.lists(), params] as const,
  details: () => [...dealKeys.all, 'detail'] as const,
  detail: (id: string) => [...dealKeys.details(), id] as const,
  pipeline: () => [...dealKeys.all, 'pipeline'] as const,
  forecast: (months?: number) => [...dealKeys.all, 'forecast', months] as const,
  calendar: (startDate?: string, endDate?: string) => [...dealKeys.all, 'calendar', startDate, endDate] as const,
};

// Fetch deals list
export function useDeals(params: DealsQueryParams = {}) {
  const { page = 1, pageSize = 50, stage, search, isArchived = false } = params;

  return useQuery<DealListResponse>({
    queryKey: dealKeys.list(params),
    queryFn: async () => {
      const searchParams = new URLSearchParams();
      searchParams.set('page', String(page));
      searchParams.set('page_size', String(pageSize));
      searchParams.set('is_archived', String(isArchived));
      if (stage) searchParams.set('stage', stage);
      if (search) searchParams.set('search', search);

      const response = await api.get<DealListResponse>(`/deals?${searchParams}`);
      return response.data;
    },
  });
}

// Fetch single deal with details
export function useDeal(dealId: string | null) {
  return useQuery<DealDetail>({
    queryKey: dealKeys.detail(dealId || ''),
    queryFn: async () => {
      const response = await api.get<DealDetail>(`/deals/${dealId}`);
      return response.data;
    },
    enabled: !!dealId,
  });
}

// Fetch pipeline summary
export function usePipelineSummary() {
  return useQuery<PipelineSummary>({
    queryKey: dealKeys.pipeline(),
    queryFn: async () => {
      const response = await api.get<PipelineSummary>('/deals/pipeline');
      return response.data;
    },
  });
}

// Fetch commission forecast
export function useCommissionForecast(months: number = 6) {
  return useQuery<CommissionForecast>({
    queryKey: dealKeys.forecast(months),
    queryFn: async () => {
      const response = await api.get<CommissionForecast>(`/deals/forecast?months=${months}`);
      return response.data;
    },
  });
}

// Fetch calendar items
export function useDealsCalendar(startDate?: string, endDate?: string) {
  return useQuery<DealCalendarItem[]>({
    queryKey: dealKeys.calendar(startDate, endDate),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (startDate) params.set('start_date', startDate);
      if (endDate) params.set('end_date', endDate);
      const response = await api.get<DealCalendarItem[]>(`/deals/calendar?${params}`);
      return response.data;
    },
  });
}

// Create deal mutation
export function useCreateDeal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: DealCreate) => {
      const response = await api.post<Deal>('/deals', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dealKeys.all });
    },
  });
}

// Update deal mutation
export function useUpdateDeal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: DealUpdate }) => {
      const response = await api.put<Deal>(`/deals/${id}`, data);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: dealKeys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: dealKeys.lists() });
      queryClient.invalidateQueries({ queryKey: dealKeys.pipeline() });
    },
  });
}

// Update deal stage mutation (with history)
export function useUpdateDealStage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: DealStageUpdate }) => {
      const response = await api.patch<Deal>(`/deals/${id}/stage`, data);
      return response.data;
    },
    // Optimistic update for smooth drag-and-drop
    onMutate: async ({ id, data }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: dealKeys.lists() });

      // Snapshot previous values
      const previousData = queryClient.getQueriesData({ queryKey: dealKeys.lists() });

      // Optimistically update lists
      queryClient.setQueriesData<DealListResponse>(
        { queryKey: dealKeys.lists() },
        (old) => {
          if (!old) return old;
          return {
            ...old,
            items: old.items.map((deal) =>
              deal.id === id ? { ...deal, stage: data.stage } : deal
            ),
          };
        }
      );

      return { previousData };
    },
    onError: (_, __, context) => {
      // Rollback on error
      if (context?.previousData) {
        context.previousData.forEach(([queryKey, data]) => {
          queryClient.setQueryData(queryKey, data);
        });
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: dealKeys.lists() });
      queryClient.invalidateQueries({ queryKey: dealKeys.pipeline() });
      queryClient.invalidateQueries({ queryKey: dealKeys.forecast() });
    },
  });
}

// Delete deal mutation
export function useDeleteDeal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/deals/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dealKeys.all });
    },
  });
}

// Add activity to deal
export function useAddDealActivity() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ dealId, data }: { dealId: string; data: DealActivityCreate }) => {
      const response = await api.post<DealActivity>(`/deals/${dealId}/activities`, data);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: dealKeys.detail(variables.dealId) });
    },
  });
}
