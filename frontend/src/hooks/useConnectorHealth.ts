import { useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/axios';
import type { ConnectorStatusItem, ConnectorProbeResult } from '../types/credentials';
import { useAuthStore } from '../stores/authStore';

// Query keys
export const connectorKeys = {
  all: ['connectors'] as const,
  status: () => [...connectorKeys.all, 'status'] as const,
};

// Sites whose user-facing login flow has been retired — data now comes in
// via direct file upload on the project property plan. The backend can
// still report their credential status (e.g., "Login failed."), but we
// don't want to nag users to "re-authenticate" when there's no login UI
// for them to hit. Keep them out of the derived issues list only;
// `useConnectorStatus` still returns them so the /connections upload
// cards continue to render.
const DEPRECATED_LOGIN_SITES = new Set(['costar', 'siteusa']);

/**
 * Fetch health status for all of the user's connectors.
 *
 * - staleTime 30s: avoids hammering the endpoint on tab switches
 * - refetchOnWindowFocus: re-checks when user returns to the tab
 */
export function useConnectorStatus() {
  const isAuthenticated = useAuthStore((s) => !!s.user);

  return useQuery<ConnectorStatusItem[]>({
    queryKey: connectorKeys.status(),
    queryFn: async () => {
      const { data } = await api.get<ConnectorStatusItem[]>('/connectors/status');
      return data;
    },
    enabled: isAuthenticated,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
    // Auto-poll every 5s while any connector is in a transitional state
    refetchInterval: (query) => {
      const statuses = query.state.data;
      if (!statuses) return false;
      const hasTransitional = statuses.some(
        (s) => s.connector_status === 'stale' || s.connector_status === 'unknown',
      );
      return hasTransitional ? 5_000 : false;
    },
  });
}

/**
 * Trigger an on-demand health probe for a specific connector.
 * Invalidates the status query on completion so the UI updates.
 */
export function useProbeConnector() {
  const queryClient = useQueryClient();

  return useMutation<ConnectorProbeResult, Error, string>({
    mutationFn: async (credentialId: string) => {
      const { data } = await api.post<ConnectorProbeResult>(
        `/connectors/${credentialId}/probe`,
      );
      return data;
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: connectorKeys.status() });
    },
  });
}

/**
 * Derived hook: connectors that need attention (needs_reauth or error).
 */
export function useConnectorIssues() {
  const { data: statuses, ...rest } = useConnectorStatus();

  const issues = useMemo(() => {
    if (!statuses) return [];
    return statuses.filter(
      (s) =>
        !DEPRECATED_LOGIN_SITES.has(s.site_name.toLowerCase()) &&
        (s.connector_status === 'needs_reauth' || s.connector_status === 'error'),
    );
  }, [statuses]);

  return {
    issues,
    count: issues.length,
    ...rest,
  };
}
