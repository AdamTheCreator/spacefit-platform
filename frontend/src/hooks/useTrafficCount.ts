import { useQuery } from '@tanstack/react-query';
import api from '../lib/axios';

// ---------------------------------------------------------------------------
// API response shape — mirrors GET /traffic/counts (backend/app/api/traffic.py).
// The endpoint always returns 200 with a `found` flag so the UI renders a clean
// empty state (uncovered state / no nearby station) rather than treating a
// missing count as an error.
// ---------------------------------------------------------------------------

/** Why a lookup returned no count. */
export type TrafficMissReason = 'ungeocodable' | 'no_station' | 'state_uncovered';

/** A real daily traffic count (AADT) from a public state-DOT source. */
export interface TrafficCountFound {
  found: true;
  covered_states: string[];
  aadt: number;
  road: string;
  year: number | null;
  distance_mi: number;
  source: string;
  state: string | null;
}

/** No count available, with a machine-readable reason for the empty state. */
export interface TrafficCountMissing {
  found: false;
  reason: TrafficMissReason;
  state?: string | null;
  covered_states: string[];
}

export type TrafficCountResponse = TrafficCountFound | TrafficCountMissing;

export const trafficKeys = {
  all: ['traffic'] as const,
  count: (address: string) => [...trafficKeys.all, 'count', address] as const,
};

/**
 * Look up the nearest official daily traffic count (AADT) for an address.
 * Disabled until `address` is a usable string (the endpoint requires >= 3 chars).
 */
export function useTrafficCount(address: string | null | undefined) {
  const trimmed = (address ?? '').trim();
  const enabled = trimmed.length >= 3;

  return useQuery({
    queryKey: trafficKeys.count(trimmed),
    enabled,
    staleTime: 24 * 60 * 60 * 1000, // AADT is annual; cache aggressively.
    queryFn: async () => {
      const res = await api.get<TrafficCountResponse>('/traffic/counts', {
        params: { address: trimmed },
      });
      return res.data;
    },
  });
}
