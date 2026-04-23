import { useQuery } from '@tanstack/react-query';

const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/api\/v1\/?$/, '');

/**
 * Lightweight health check that pings the backend every 30s.
 * Returns a connection status suitable for the topbar indicator.
 */
export function useApiHealth() {
  const { isSuccess, isError, isFetching, isLoading } = useQuery({
    queryKey: ['api-health'],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/health`, {
        method: 'GET',
        mode: 'cors',
        credentials: 'omit',
      });
      if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
      return true;
    },
    refetchInterval: 30_000,
    retry: 1,
    staleTime: 25_000,
  });

  if (isLoading) return 'connecting' as const;
  if (isSuccess && !isError) return 'connected' as const;
  if (isError && !isFetching) return 'disconnected' as const;
  return 'connecting' as const;
}
