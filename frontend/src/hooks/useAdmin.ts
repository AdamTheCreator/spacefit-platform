import { useQuery } from '@tanstack/react-query';
import api from '../lib/axios';

// --- Types ---

export interface SignupBucket {
  date: string;
  count: number;
}

export interface AdminOverview {
  total_users: number;
  active_users_30d: number;
  new_users_7d: number;
  new_users_30d: number;
  total_sessions: number;
  total_documents: number;
  total_deals: number;
  total_projects: number;
  signups_over_time: SignupBucket[];
}

export interface AdminUserSummary {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  tier: string;
  is_active: boolean;
  session_count: number;
  document_count: number;
  deal_count: number;
  project_count: number;
  created_at: string;
  last_active: string | null;
}

export interface AdminUserList {
  users: AdminUserSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface TokenUsageSummary {
  period_start: string;
  input_tokens: number;
  output_tokens: number;
  llm_calls: number;
}

export interface RecentSession {
  id: string;
  title: string | null;
  message_count: number;
  created_at: string;
}

export interface AdminUserDetail {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  tier: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  session_count: number;
  document_count: number;
  deal_count: number;
  project_count: number;
  token_usage: TokenUsageSummary[];
  recent_sessions: RecentSession[];
}

export interface TopConsumer {
  user_id: string;
  email: string;
  input_tokens: number;
  output_tokens: number;
  llm_calls: number;
  total_tokens: number;
}

export interface AdminUsage {
  period_label: string;
  total_input_tokens: number;
  total_output_tokens: number;
  total_llm_calls: number;
  top_consumers: TopConsumer[];
}

export interface AbuseFlag {
  user_id: string;
  email: string;
  reason: string;
  severity: string;
  detail: string;
}

export interface AdminAbuse {
  flags: AbuseFlag[];
}

// --- Fetchers ---

async function fetchOverview(): Promise<AdminOverview> {
  const { data } = await api.get<AdminOverview>('/admin/overview');
  return data;
}

async function fetchUsers(page: number, search: string): Promise<AdminUserList> {
  const { data } = await api.get<AdminUserList>('/admin/users', {
    params: { page, search: search || undefined },
  });
  return data;
}

async function fetchUserDetail(userId: string): Promise<AdminUserDetail> {
  const { data } = await api.get<AdminUserDetail>(`/admin/users/${userId}`);
  return data;
}

async function fetchUsage(): Promise<AdminUsage> {
  const { data } = await api.get<AdminUsage>('/admin/usage');
  return data;
}

async function fetchAbuse(): Promise<AdminAbuse> {
  const { data } = await api.get<AdminAbuse>('/admin/abuse');
  return data;
}

// --- Hooks ---

export function useAdminOverview() {
  return useQuery({
    queryKey: ['admin', 'overview'],
    queryFn: fetchOverview,
    staleTime: 1000 * 60 * 2,
  });
}

export function useAdminUsers(page: number = 1, search: string = '') {
  return useQuery({
    queryKey: ['admin', 'users', page, search],
    queryFn: () => fetchUsers(page, search),
    staleTime: 1000 * 60 * 2,
  });
}

export function useAdminUserDetail(userId: string | null) {
  return useQuery({
    queryKey: ['admin', 'user', userId],
    queryFn: () => fetchUserDetail(userId!),
    enabled: !!userId,
    staleTime: 1000 * 60 * 2,
  });
}

export function useAdminUsage() {
  return useQuery({
    queryKey: ['admin', 'usage'],
    queryFn: fetchUsage,
    staleTime: 1000 * 60 * 2,
  });
}

export function useAdminAbuse() {
  return useQuery({
    queryKey: ['admin', 'abuse'],
    queryFn: fetchAbuse,
    staleTime: 1000 * 60 * 2,
  });
}
