import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/axios';
import { useAuthStore } from '../stores/authStore';

export interface PreferenceOption {
  value: string;
  label: string;
  description: string;
}

export interface PreferencesOptions {
  roles: PreferenceOption[];
  property_types: PreferenceOption[];
  tenant_categories: PreferenceOption[];
  analysis_priorities: PreferenceOption[];
}

export interface UserPreferences {
  id: string;
  role: string | null;
  property_types: string[];
  tenant_categories: string[];
  markets: string[];
  deal_size_min: number | null;
  deal_size_max: number | null;
  key_tenants: string[];
  analysis_priorities: string[];
  custom_notes: string | null;
  is_complete: boolean;
  completion_percentage: number;
  created_at: string;
  updated_at: string;
}

export interface PreferencesUpdate {
  role?: string | null;
  property_types?: string[];
  tenant_categories?: string[];
  markets?: string[];
  deal_size_min?: number | null;
  deal_size_max?: number | null;
  key_tenants?: string[];
  analysis_priorities?: string[];
  custom_notes?: string | null;
}

async function fetchPreferencesOptions(): Promise<PreferencesOptions> {
  const { data } = await api.get<PreferencesOptions>('/preferences/options');
  return data;
}

async function fetchPreferences(): Promise<UserPreferences> {
  const { data } = await api.get<UserPreferences>('/preferences');
  return data;
}

async function updatePreferences(data: PreferencesUpdate): Promise<UserPreferences> {
  const { data: responseData } = await api.put<UserPreferences>(
    '/preferences',
    data,
  );
  return responseData;
}

export function usePreferencesOptions() {
  return useQuery({
    queryKey: ['preferencesOptions'],
    queryFn: fetchPreferencesOptions,
    staleTime: 1000 * 60 * 60, // 1 hour - options don't change often
  });
}

export function usePreferences() {
  const { user } = useAuthStore();

  return useQuery({
    queryKey: ['preferences', user?.id],
    queryFn: fetchPreferences,
    enabled: !!user,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

export function useUpdatePreferences() {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();

  return useMutation({
    mutationFn: updatePreferences,
    onSuccess: (data) => {
      queryClient.setQueryData(['preferences', user?.id], data);
    },
  });
}
