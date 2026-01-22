import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../stores/authStore';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

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

async function getAuthHeaders(): Promise<HeadersInit> {
  const token = localStorage.getItem('access_token');
  return {
    'Content-Type': 'application/json',
    Authorization: token ? `Bearer ${token}` : '',
  };
}

async function fetchPreferencesOptions(): Promise<PreferencesOptions> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/preferences/options`, { headers });
  if (!response.ok) throw new Error('Failed to fetch preference options');
  return response.json();
}

async function fetchPreferences(): Promise<UserPreferences> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/preferences`, { headers });
  if (!response.ok) throw new Error('Failed to fetch preferences');
  return response.json();
}

async function updatePreferences(data: PreferencesUpdate): Promise<UserPreferences> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/preferences`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error('Failed to update preferences');
  return response.json();
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
