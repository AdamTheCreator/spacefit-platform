import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/axios';

export interface GmailStatus {
  connected: boolean;
  email: string | null;
}

const gmailStatusKey = ['gmailConnection', 'status'] as const;

export function useGmailStatus() {
  return useQuery({
    queryKey: gmailStatusKey,
    queryFn: async () => {
      const res = await api.get<GmailStatus>('/auth/gmail/status');
      return res.data;
    },
  });
}

// Connecting can't be a plain fetch: the consent flow is a top-level browser
// navigation. We fetch the signed consent URL (Bearer-authenticated) and then
// hand the browser off to Google.
export function useConnectGmail() {
  return useMutation({
    mutationFn: async () => {
      const res = await api.get<{ authorization_url: string }>(
        '/auth/gmail/authorize'
      );
      return res.data.authorization_url;
    },
    onSuccess: (url) => {
      window.location.href = url;
    },
  });
}

export function useDisconnectGmail() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await api.delete('/auth/gmail');
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: gmailStatusKey });
    },
  });
}

export { gmailStatusKey };
