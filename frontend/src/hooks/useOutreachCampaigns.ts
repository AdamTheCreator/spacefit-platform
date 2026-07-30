import { useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/axios';
import { dealKeys } from './useDeals';
import type { SendCampaignResponse } from '../types/outreach';

export const outreachKeys = {
  all: ['outreach'] as const,
  campaigns: () => [...outreachKeys.all, 'campaigns'] as const,
  campaign: (id: string) => [...outreachKeys.campaigns(), id] as const,
};

/**
 * Send an outreach campaign. On success invalidates the deal caches (a sent
 * campaign drops a deal card onto the Workflow board) plus any campaign query
 * state, so the deal-cache invalidation lives in exactly one place.
 */
export function useSendCampaign() {
  const queryClient = useQueryClient();

  return useMutation<SendCampaignResponse, unknown, string>({
    mutationFn: async (campaignId: string) => {
      const { data } = await api.post<SendCampaignResponse>(
        `/outreach/campaigns/${campaignId}/send`,
      );
      return data;
    },
    onSuccess: (_data, campaignId) => {
      queryClient.invalidateQueries({ queryKey: dealKeys.all });
      queryClient.invalidateQueries({ queryKey: outreachKeys.campaigns() });
      queryClient.invalidateQueries({ queryKey: outreachKeys.campaign(campaignId) });
    },
  });
}

/** Extract a backend `detail` message (e.g. 400s) for a user-facing toast. */
export function sendCampaignErrorMessage(err: unknown): string {
  const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return detail || 'Failed to send campaign';
}
