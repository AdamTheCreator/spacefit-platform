import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import api from '../lib/axios';

export type FactStatus = 'pending' | 'approved' | 'rejected' | 'archived';

export interface UserFact {
  id: string;
  text: string;
  category: string;
  status: FactStatus;
  confidence: number;
  source_session_id?: string | null;
  source_message_id?: string | null;
  created_at: string;
  approved_at?: string | null;
  last_used_at?: string | null;
}

export function useUserFacts(statusFilter?: FactStatus) {
  return useQuery({
    queryKey: ['userFacts', statusFilter ?? 'all'],
    queryFn: async () => {
      const params = statusFilter ? { status_filter: statusFilter } : undefined;
      const response = await api.get<UserFact[]>('/users/me/memory/facts', {
        params,
      });
      return response.data;
    },
    staleTime: 30_000,
  });
}

export function useApproveFact() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (factId: string) => {
      const response = await api.post<UserFact>(
        `/users/me/memory/facts/${factId}/approve`,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['userFacts'] });
    },
  });
}

export function useRejectFact() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (factId: string) => {
      const response = await api.post<UserFact>(
        `/users/me/memory/facts/${factId}/reject`,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['userFacts'] });
    },
  });
}

export function useArchiveFact() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (factId: string) => {
      await api.delete(`/users/me/memory/facts/${factId}`);
      return factId;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['userFacts'] });
    },
  });
}
