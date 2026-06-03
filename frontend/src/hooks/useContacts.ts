import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/axios';
import type {
  Company,
  Contact,
  Interaction,
  VerificationStatus,
  ContactSource,
} from '../pages/contacts/data';
import type { TenantCandidate } from '../types/chat';

// ---------------------------------------------------------------------------
// API response shapes (snake_case, timestamps) + adapters to the UI interfaces.
// The directory components keep consuming the existing Company/Contact/Interaction
// shapes; the adapter derives the relative-day deltas the UI expects from the
// stored timestamps, so the components barely change.
// ---------------------------------------------------------------------------

interface CompanyApi {
  id: string;
  name: string;
  sector: string | null;
  subsector: string | null;
  us_locations: number | null;
  is_expanding: boolean | null;
  target_markets: string[] | null;
  sf_min: number | null;
  sf_max: number | null;
  website: string | null;
  criteria: Record<string, unknown> | null;
  notes: string | null;
  enriched_at: string | null;
  created_at: string;
  updated_at: string;
}

interface ContactApi {
  id: string;
  company_id: string;
  first: string;
  last: string | null;
  role: string | null;
  email: string | null;
  phone: string | null;
  verif: VerificationStatus;
  source: ContactSource;
  linkedin: boolean;
  notes: string | null;
  last_verified_at: string | null;
  last_contacted_at: string | null;
  last_reply_at: string | null;
  created_at: string;
  updated_at: string;
}

interface InteractionApi {
  id: string;
  contact_id: string;
  type: string;
  occurred_at: string;
  who: string | null;
  title: string | null;
  summary: string;
  created_at: string;
}

interface Paged<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

function daysSince(iso: string | null): number | null {
  if (!iso) return null;
  const ms = Date.now() - new Date(iso).getTime();
  if (Number.isNaN(ms)) return null;
  return Math.max(0, Math.floor(ms / 86_400_000));
}

function toCompany(r: CompanyApi): Company {
  return {
    id: r.id,
    name: r.name,
    sector: r.sector ?? '',
    subsector: r.subsector ?? '',
    us_locations: r.us_locations ?? 0,
    is_expanding: r.is_expanding,
    target_markets: r.target_markets ?? [],
    sf_min: r.sf_min ?? 0,
    sf_max: r.sf_max ?? 0,
    website: r.website ?? '',
    notes: r.notes ?? '',
    enriched_days: daysSince(r.enriched_at),
  };
}

function toContact(r: ContactApi): Contact {
  return {
    id: r.id,
    company_id: r.company_id,
    first: r.first,
    last: r.last ?? '',
    role: r.role ?? '',
    email: r.email,
    phone: r.phone,
    verif: r.verif,
    last_verified_days: daysSince(r.last_verified_at),
    last_contacted_days: daysSince(r.last_contacted_at),
    last_reply_days: daysSince(r.last_reply_at),
    source: r.source,
    linkedin: r.linkedin,
    notes: r.notes ?? '',
  };
}

function toInteraction(r: InteractionApi): Interaction {
  return {
    id: r.id,
    contact_id: r.contact_id,
    type: r.type as Interaction['type'],
    when_days: daysSince(r.occurred_at) ?? 0,
    who: r.who ?? '',
    title: r.title ?? undefined,
    summary: r.summary,
  };
}

// ---------------------------------------------------------------------------
// Inputs
// ---------------------------------------------------------------------------

export interface CompanyInput {
  name: string;
  sector?: string | null;
  subsector?: string | null;
  us_locations?: number | null;
  is_expanding?: boolean | null;
  target_markets?: string[] | null;
  sf_min?: number | null;
  sf_max?: number | null;
  website?: string | null;
  criteria?: Record<string, unknown> | null;
  notes?: string | null;
}

export interface ContactInput {
  first: string;
  last?: string | null;
  role?: string | null;
  email?: string | null;
  phone?: string | null;
  verif?: VerificationStatus;
  source?: ContactSource;
  linkedin?: boolean;
  notes?: string | null;
  // Attach to an existing company or auto-create one by name.
  company_id?: string;
  company_name?: string;
}

export interface ImportContactsResult {
  imported: number;
  failed: number;
  companies_created: number;
  errors: string[];
}

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

export const contactKeys = {
  all: ['contacts'] as const,
  companies: () => [...contactKeys.all, 'companies'] as const,
  company: (id: string) => [...contactKeys.all, 'company', id] as const,
  contacts: (companyId?: string) =>
    [...contactKeys.all, 'contacts', companyId ?? 'all'] as const,
  contact: (id: string) => [...contactKeys.all, 'contact', id] as const,
  interactions: (id: string) => [...contactKeys.all, 'interactions', id] as const,
};

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

export function useCompanies() {
  return useQuery({
    queryKey: contactKeys.companies(),
    queryFn: async () => {
      const res = await api.get<Paged<CompanyApi>>('/companies?page_size=1000');
      return res.data.items.map(toCompany);
    },
  });
}

export function useContacts(companyId?: string) {
  return useQuery({
    queryKey: contactKeys.contacts(companyId),
    queryFn: async () => {
      const qs = companyId
        ? `?company_id=${encodeURIComponent(companyId)}&page_size=1000`
        : '?page_size=1000';
      const res = await api.get<Paged<ContactApi>>(`/contacts${qs}`);
      return res.data.items.map(toContact);
    },
  });
}

export function useCompany(id: string | null) {
  return useQuery({
    queryKey: contactKeys.company(id ?? ''),
    enabled: !!id,
    queryFn: async () => {
      const res = await api.get<CompanyApi>(`/companies/${id}`);
      return toCompany(res.data);
    },
  });
}

export function useContact(id: string | null) {
  return useQuery({
    queryKey: contactKeys.contact(id ?? ''),
    enabled: !!id,
    queryFn: async () => {
      const res = await api.get<ContactApi>(`/contacts/${id}`);
      return toContact(res.data);
    },
  });
}

export function useContactInteractions(id: string | null) {
  return useQuery({
    queryKey: contactKeys.interactions(id ?? ''),
    enabled: !!id,
    queryFn: async () => {
      const res = await api.get<InteractionApi[]>(`/contacts/${id}/interactions`);
      return res.data.map(toInteraction);
    },
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

export function useCreateCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: CompanyInput) => {
      const res = await api.post<CompanyApi>('/companies', data);
      return toCompany(res.data);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: contactKeys.all }),
  });
}

export function useUpdateCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<CompanyInput> }) => {
      const res = await api.patch<CompanyApi>(`/companies/${id}`, data);
      return toCompany(res.data);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: contactKeys.all }),
  });
}

export function useDeleteCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/companies/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: contactKeys.all }),
  });
}

export function useCreateContact() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: ContactInput) => {
      const res = await api.post<ContactApi>('/contacts', data);
      return toContact(res.data);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: contactKeys.all }),
  });
}

export function useUpdateContact() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<ContactInput> }) => {
      const res = await api.patch<ContactApi>(`/contacts/${id}`, data);
      return toContact(res.data);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: contactKeys.all }),
  });
}

export function useDeleteContact() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/contacts/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: contactKeys.all }),
  });
}

export function useImportContacts() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      const res = await api.post<ImportContactsResult>('/contacts/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: contactKeys.all }),
  });
}

export interface PromoteTenantsResult {
  created: number;
  skipped: number;
  companies: { id: string; name: string; sector: string | null }[];
}

/** Save void/matchmaker tenant suggestions into the Contacts directory. */
export function usePromoteTenantsFromVoid() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      tenants: TenantCandidate[];
      source_address?: string | null;
      project_id?: string | null;
    }) => {
      const res = await api.post<PromoteTenantsResult>('/contacts/from-void', data);
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: contactKeys.all }),
  });
}

export interface InteractionInput {
  type?: Interaction['type'];
  summary: string;
  who?: string | null;
  title?: string | null;
  occurred_at?: string | null;
}

export function useAddInteraction(contactId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: InteractionInput) => {
      const res = await api.post<InteractionApi>(
        `/contacts/${contactId}/interactions`,
        data,
      );
      return toInteraction(res.data);
    },
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: contactKeys.interactions(contactId) }),
  });
}
