import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/axios';

// ---------------------------------------------------------------------------
// API response shapes — mirror the backend Pydantic schemas exactly
// (backend/app/api/outreach_voice.py). Field names map 1:1 to
// VoiceProfileResponse / DraftRequest / DraftResponse.
// ---------------------------------------------------------------------------

/** Mirrors `VoiceProfileResponse`. */
export interface VoiceProfile {
  id: string;
  name: string;
  instructions: string;
  tone: string | null;
  sample: string | null;
  signature: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

/** Mirrors `VoiceProfileCreate`. */
export interface VoiceProfileCreate {
  name: string;
  instructions: string;
  tone?: string | null;
  sample?: string | null;
  signature?: string | null;
  is_default?: boolean;
}

/** Mirrors `VoiceProfileUpdate` (all fields optional). */
export type VoiceProfileUpdate = Partial<VoiceProfileCreate>;

/** Mirrors `DraftRequest`. */
export interface DraftRequest {
  voice_id?: string | null;
  property_name?: string | null;
  property_address?: string | null;
  vacancy_description?: string | null;
  tenant_name?: string | null;
  recipient_company?: string | null;
  extra_notes?: string | null;
}

/** Mirrors `DraftResponse`. */
export interface DraftResponse {
  subject: string;
  body: string;
  used_voice_id: string | null;
  model: string;
  is_byok: boolean;
  /** True when the LLM path failed and a static template draft was returned. */
  fallback_used: boolean;
}

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

export const voiceKeys = {
  all: ['outreachVoices'] as const,
  list: () => [...voiceKeys.all, 'list'] as const,
};

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

export function useOutreachVoices() {
  return useQuery({
    queryKey: voiceKeys.list(),
    queryFn: async () => {
      const res = await api.get<VoiceProfile[]>('/outreach/voices');
      return res.data;
    },
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

export function useCreateVoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: VoiceProfileCreate) => {
      const res = await api.post<VoiceProfile>('/outreach/voices', data);
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: voiceKeys.all }),
  });
}

export function useUpdateVoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: VoiceProfileUpdate }) => {
      const res = await api.put<VoiceProfile>(`/outreach/voices/${id}`, data);
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: voiceKeys.all }),
  });
}

export function useDeleteVoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/outreach/voices/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: voiceKeys.all }),
  });
}

export function useSetDefaultVoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await api.post<VoiceProfile>(`/outreach/voices/${id}/default`, {});
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: voiceKeys.all }),
  });
}

/**
 * Generate an outreach email draft (subject + body) in the user's voice.
 * Not cached — it's a one-shot generation the composer drops into the editor.
 */
export function useGenerateDraft() {
  return useMutation({
    mutationFn: async (data: DraftRequest) => {
      const res = await api.post<DraftResponse>('/outreach/draft-ai', data);
      return res.data;
    },
  });
}
