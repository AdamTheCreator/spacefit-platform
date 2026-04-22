/**
 * Audit-log hook (BYOK v2).
 *
 * Feeds the "Recent activity" subsection on the Settings AI card.
 * Route 404s when the backend's `BYOK_REBUILD_ENABLED` flag is off —
 * the hook returns an empty list in that case via React Query's error
 * handling, so the UI degrades silently.
 */

import { useQuery } from '@tanstack/react-query';

import api from '../lib/axios';
import { useAuthStore } from '../stores/authStore';

export interface CredentialAuditEntry {
  id: number;
  action: string;
  success: boolean;
  provider: string | null;
  error_code: string | null;
  request_id: string | null;
  metadata: Record<string, unknown>;
  occurred_at: string;
}

/**
 * GET /ai-config/audit?limit=N — pull the most recent audit rows for
 * the current user. Tolerates v1 backends (route 404s) by returning
 * an empty list instead of surfacing the error; callers can show
 * "No activity yet" either way.
 */
export function useCredentialAudit(limit = 20) {
  const { user } = useAuthStore();
  return useQuery<CredentialAuditEntry[]>({
    queryKey: ['credentialAudit', user?.id, limit],
    queryFn: async () => {
      try {
        const { data } = await api.get<CredentialAuditEntry[]>('/ai-config/audit', {
          params: { limit },
        });
        return data;
      } catch (err: unknown) {
        // Route doesn't exist on a v1 backend — treat as empty list
        // rather than an error state so the UI can still render.
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 404) return [];
        throw err;
      }
    },
    enabled: !!user,
    staleTime: 1000 * 30, // 30s — activity should feel fresh
    // 404 (feature flag off) is deterministic; queryFn already coerces it
    // to []. Don't retry on any other status either — audit failures are
    // informational and shouldn't slow the Settings page down.
    retry: 0,
  });
}

/**
 * Turn an audit action string into a human label for display.
 * Keeps the action enum in one place so the Settings card can
 * render a consistent activity feed.
 */
export function auditActionLabel(action: string): string {
  switch (action) {
    case 'credential.create':
      return 'Key added';
    case 'credential.validate':
      return 'Key validated';
    case 'credential.use':
      return 'Key used';
    case 'credential.use_failed':
      return 'Key call failed';
    case 'credential.rotate_start':
      return 'Rotation started';
    case 'credential.rotate_complete':
      return 'Rotation completed';
    case 'credential.revoke':
      return 'Key removed';
    case 'credential.auto_invalidate':
      return 'Auto-invalidated';
    case 'credential.scope_update':
      return 'Scope updated';
    case 'credential.view_metadata':
      return 'Settings viewed';
    default:
      // Unknown action — show the raw token so operators can spot it.
      return action.replace(/^credential\./, '').replace(/_/g, ' ');
  }
}
