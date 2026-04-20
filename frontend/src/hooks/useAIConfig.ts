import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/axios';
import { useAuthStore } from '../stores/authStore';

export interface AIConfig {
  provider: string;
  model: string | null;
  base_url: string | null;
  has_byok_key: boolean;
  is_key_valid: boolean;
  key_validated_at: string | null;
  key_error_message: string | null;
  effective_provider: string;
  effective_model: string;
}

export interface AIConfigUpdate {
  provider: string;
  model?: string | null;
  api_key?: string | null;
  base_url?: string | null;
}

export interface ValidateKeyRequest {
  provider: string;
  api_key: string;
  model?: string | null;
  base_url?: string | null;
}

export interface ValidateKeyResponse {
  valid: boolean;
  error: string | null;
  model_tested: string | null;
}

export interface ProviderInfo {
  id: string;
  name: string;
  description: string;
  requires_key: boolean;
  requires_base_url: boolean;
  default_model: string;
  models: string[];
}

async function fetchAIConfig(): Promise<AIConfig> {
  const { data } = await api.get<AIConfig>('/ai-config');
  return data;
}

async function updateAIConfig(data: AIConfigUpdate): Promise<AIConfig> {
  const { data: responseData } = await api.put<AIConfig>('/ai-config', data);
  return responseData;
}

async function validateKey(data: ValidateKeyRequest): Promise<ValidateKeyResponse> {
  const { data: responseData } = await api.post<ValidateKeyResponse>(
    '/ai-config/validate-key',
    data,
  );
  return responseData;
}

async function removeKey(): Promise<AIConfig> {
  const { data } = await api.delete<AIConfig>('/ai-config/key');
  return data;
}

async function fetchProviders(): Promise<ProviderInfo[]> {
  const { data } = await api.get<ProviderInfo[]>('/ai-config/providers');
  return data;
}

export function useAIConfig() {
  const { user } = useAuthStore();
  return useQuery({
    queryKey: ['aiConfig', user?.id],
    queryFn: fetchAIConfig,
    enabled: !!user,
    staleTime: 1000 * 60 * 5,
  });
}

export function useUpdateAIConfig() {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  return useMutation({
    mutationFn: updateAIConfig,
    onSuccess: (data) => {
      queryClient.setQueryData(['aiConfig', user?.id], data);
    },
  });
}

export function useValidateKey() {
  return useMutation({
    mutationFn: validateKey,
  });
}

export function useRemoveKey() {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  return useMutation({
    mutationFn: removeKey,
    onSuccess: (data) => {
      queryClient.setQueryData(['aiConfig', user?.id], data);
    },
  });
}

export function useProviders() {
  return useQuery({
    queryKey: ['aiProviders'],
    queryFn: fetchProviders,
    staleTime: 1000 * 60 * 60, // 1 hour
  });
}

// --- Usage ---

export interface UsageData {
  last_24h_total_tokens: number;
  last_24h_llm_calls: number;
  last_24h_cost_estimate_usd: number;
  using_byok: boolean;
  current_period_input_tokens: number;
  current_period_output_tokens: number;
}

export function useUsage() {
  const { user } = useAuthStore();
  return useQuery({
    queryKey: ['aiUsage', user?.id],
    queryFn: async () => {
      const { data } = await api.get<UsageData>('/ai-config/usage');
      return data;
    },
    enabled: !!user,
    staleTime: 1000 * 30, // 30s
  });
}

// --- Specialist model overrides ---

export interface SpecialistModels {
  specialist_models: Record<string, string>;
}

export function useSpecialistModels() {
  const { user } = useAuthStore();
  return useQuery({
    queryKey: ['specialistModels', user?.id],
    queryFn: async () => {
      const { data } = await api.get<SpecialistModels>('/ai-config/specialist-models');
      return data;
    },
    enabled: !!user,
    staleTime: 1000 * 60 * 5,
  });
}

export function useUpdateSpecialistModels() {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  return useMutation({
    mutationFn: async (models: Record<string, string>) => {
      const { data } = await api.put<SpecialistModels>('/ai-config/specialist-models', {
        specialist_models: models,
      });
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(['specialistModels', user?.id], data);
    },
  });
}
