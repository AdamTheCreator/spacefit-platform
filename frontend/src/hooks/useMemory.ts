import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/axios';

export interface AnalyzedProperty {
  address: string;
  asset_type: string;
  analysis_date: string;
  key_findings: string[];
  void_count: number;
}

export interface BookOfBusinessSummary {
  tenant_count: number;
  top_categories: string[];
  coverage_areas: string[];
  last_import?: string;
}

export interface UserPreferences {
  preferred_asset_types: string[];
  preferred_trade_areas: string[];
  typical_sf_range?: { min: number; max: number };
}

export interface UserMemory {
  id: string;
  total_analyses: number;
  analyzed_properties: AnalyzedProperty[];
  book_of_business_summary?: BookOfBusinessSummary;
  preferences: UserPreferences;
  ai_profile_summary?: string;
  last_updated: string;
}

export interface MemoryStats {
  total_analyses: number;
  properties_count: number;
  tenant_count: number;
  has_memory: boolean;
}

export function useMemory() {
  return useQuery<UserMemory | null>({
    queryKey: ['userMemory'],
    queryFn: async () => {
      const response = await api.get<UserMemory | null>('/users/me/memory');
      return response.data;
    },
  });
}

export function useMemoryStats() {
  return useQuery<MemoryStats>({
    queryKey: ['userMemoryStats'],
    queryFn: async () => {
      const response = await api.get<MemoryStats>('/users/me/memory/stats');
      return response.data;
    },
  });
}

export function useClearMemory() {
  const queryClient = useQueryClient();

  return useMutation<void, Error>({
    mutationFn: async () => {
      await api.delete('/users/me/memory');
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['userMemory'] });
      queryClient.invalidateQueries({ queryKey: ['userMemoryStats'] });
    },
  });
}
