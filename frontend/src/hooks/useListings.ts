import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/axios';

// ---------------------------------------------------------------------------
// API response shapes — mirror the backend Pydantic schemas exactly
// (backend/app/models/listing.py). Field names are NOT guessed; they map
// 1:1 to ListingResponse / MatchedListing / MatchResponse / ListingImportResult.
// ---------------------------------------------------------------------------

/** Mirrors `ListingResponse` (ListingBase + id/source/timestamps). */
export interface Listing {
  id: string;
  address: string | null;
  city: string | null;
  state: string | null;
  zip_code: string | null;
  asset_type: string | null;
  size_sf: number | null;
  price: number | null;
  cap_rate: number | null;
  year_built: number | null;
  units: number | null;
  listing_url: string | null;
  description: string | null;
  source: string;
  created_at: string;
  updated_at: string;
}

/** Mirrors `ListingListResponse`. */
interface ListingListResponse {
  items: Listing[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

/** Mirrors `MatchedListing`. */
export interface MatchedListing {
  listing: Listing;
  fit_score: number;
  rationale: string;
  flags: string[];
}

/** Mirrors `MatchResponse`. */
export interface MatchResponse {
  client_name: string;
  matches: MatchedListing[];
}

/** Mirrors `ListingImportResult`. */
export interface ImportListingsResult {
  imported: number;
  failed: number;
  errors: string[];
}

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

export const listingKeys = {
  all: ['listings'] as const,
  list: () => [...listingKeys.all, 'list'] as const,
};

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

export function useListings() {
  return useQuery({
    queryKey: listingKeys.list(),
    queryFn: async () => {
      const res = await api.get<ListingListResponse>('/listings?page_size=1000');
      return res.data.items;
    },
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

export function useImportListings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      const res = await api.post<ImportListingsResult>('/listings/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: listingKeys.all }),
  });
}

export function useDeleteListing() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/listings/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: listingKeys.all }),
  });
}

export function useMatchListings() {
  return useMutation({
    mutationFn: async (vars: { company_id: string; limit?: number }) => {
      const res = await api.post<MatchResponse>('/listings/match', vars);
      return res.data;
    },
  });
}
