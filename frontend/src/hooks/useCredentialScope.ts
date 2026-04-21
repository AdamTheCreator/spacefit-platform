/**
 * Governance scope hooks (BYOK v2).
 *
 * Scope lives on the active credential row and restricts which models
 * may be used and how much the credential can spend in a month. These
 * routes 404 when the backend's `BYOK_REBUILD_ENABLED` flag is off —
 * UI should gate the scope panel on a v2 response shape (presence of
 * `id` in the `AIConfig` payload) rather than assume availability.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';

import api from '../lib/axios';
import { useAuthStore } from '../stores/authStore';

export interface CredentialScope {
  allowed_models?: string[];
  denied_models?: string[];
  monthly_spend_cap_usd?: number;
  monthly_request_cap?: number;
}

export interface ScopeUpdatePayload {
  allowed_models?: string[] | null;
  denied_models?: string[] | null;
  monthly_spend_cap_usd?: number | null;
  monthly_request_cap?: number | null;
}

/**
 * PUT /ai-config/scope — update scope on the active credential.
 *
 * Invalidates the `['aiConfig', userId]` query so the Settings card
 * reflects the new scope without a manual refresh.
 */
export function useUpdateCredentialScope() {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  return useMutation({
    mutationFn: async (payload: ScopeUpdatePayload) => {
      const { data } = await api.put('/ai-config/scope', payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['aiConfig', user?.id] });
    },
  });
}
