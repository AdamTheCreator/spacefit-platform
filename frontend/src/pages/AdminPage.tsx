import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import {
  Users,
  Activity,
  FileText,
  FolderOpen,
  Kanban,
  Search,
  Shield,
  AlertTriangle,
  CheckCircle2,
  Loader2,
} from 'lucide-react';
import { AppLayout } from '../components/Layout';
import { useAuthStore } from '../stores/authStore';
import {
  useAdminOverview,
  useAdminUsers,
  useAdminUserDetail,
  useAdminUsage,
  useAdminAbuse,
} from '../hooks/useAdmin';
import type { AdminUserSummary } from '../hooks/useAdmin';
import { DataTable, type Column } from '../components/ui/DataTable';
import { SideDrawer } from '../components/ui/SideDrawer';

function StatCard({ label, value, icon: Icon }: { label: string; value: number | string; icon: React.ElementType }) {
  return (
    <div className="p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-subtle)]">
      <div className="flex items-center gap-2 mb-1">
        <Icon size={14} className="text-industrial-muted" />
        <span className="text-xs text-industrial-muted">{label}</span>
      </div>
      <p className="text-2xl font-bold text-industrial">{typeof value === 'number' ? value.toLocaleString() : value}</p>
    </div>
  );
}

function SignupChart({ data }: { data: { date: string; count: number }[] }) {
  if (data.length === 0) return null;
  const max = Math.max(...data.map(d => d.count), 1);

  return (
    <div className="mt-6">
      <p className="text-xs text-industrial-muted mb-3">Signups — last 90 days</p>
      <div className="flex items-end gap-px h-24">
        {data.map((d) => (
          <div
            key={d.date}
            className="flex-1 bg-[var(--accent)] rounded-t opacity-70 hover:opacity-100 transition-opacity min-w-[2px]"
            style={{ height: `${(d.count / max) * 100}%` }}
            title={`${d.date}: ${d.count}`}
          />
        ))}
      </div>
    </div>
  );
}

function OverviewSection() {
  const { data, isLoading } = useAdminOverview();

  if (isLoading) return <SectionLoader />;
  if (!data) return null;

  return (
    <section className="mb-10">
      <h2 className="text-sm font-bold text-industrial mb-4">Overview</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Total users" value={data.total_users} icon={Users} />
        <StatCard label="Active (30d)" value={data.active_users_30d} icon={Activity} />
        <StatCard label="New (7d)" value={data.new_users_7d} icon={Users} />
        <StatCard label="Sessions" value={data.total_sessions} icon={Activity} />
        <StatCard label="Documents" value={data.total_documents} icon={FileText} />
        <StatCard label="Deals" value={data.total_deals} icon={Kanban} />
        <StatCard label="Projects" value={data.total_projects} icon={FolderOpen} />
        <StatCard label="New (30d)" value={data.new_users_30d} icon={Users} />
      </div>
      <SignupChart data={data.signups_over_time} />
    </section>
  );
}

function UserDetailDrawer({ user, onClose }: { user: AdminUserSummary | null; onClose: () => void }) {
  const { data: detail, isLoading } = useAdminUserDetail(user?.id ?? null);

  return (
    <SideDrawer open={!!user} onClose={onClose} title={user?.email ?? 'User'}>
      <div className="p-6">
        {isLoading ? (
          <div className="flex items-center gap-2 text-xs text-industrial-muted py-2">
            <Loader2 size={12} className="animate-spin" /> Loading...
          </div>
        ) : detail ? (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-4 text-xs text-industrial-secondary">
              <span>Tier: <strong>{detail.tier}</strong></span>
              <span>Active: {detail.is_active ? 'Yes' : 'No'}</span>
              <span>Admin: {detail.is_admin ? 'Yes' : 'No'}</span>
              <span>Sessions: {detail.session_count}</span>
              <span>Docs: {detail.document_count}</span>
              <span>Deals: {detail.deal_count}</span>
              <span>Projects: {detail.project_count}</span>
            </div>

            {detail.token_usage.length > 0 && (
              <div>
                <p className="text-xs text-industrial-muted mb-1">Token usage</p>
                <div className="flex flex-wrap gap-3">
                  {detail.token_usage.map((t) => (
                    <div key={t.period_start} className="text-xs text-industrial-secondary">
                      <span className="text-industrial-muted">{new Date(t.period_start).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}:</span>{' '}
                      {(t.input_tokens + t.output_tokens).toLocaleString()} tokens, {t.llm_calls} calls
                    </div>
                  ))}
                </div>
              </div>
            )}

            {detail.recent_sessions.length > 0 && (
              <div>
                <p className="text-xs text-industrial-muted mb-1">Recent sessions</p>
                <div className="space-y-1">
                  {detail.recent_sessions.slice(0, 5).map((s) => (
                    <div key={s.id} className="text-xs text-industrial-secondary flex items-center gap-2">
                      <span className="text-industrial-muted">{new Date(s.created_at).toLocaleDateString()}</span>
                      <span className="truncate max-w-xs">{s.title || 'Untitled'}</span>
                      <span className="text-industrial-muted">({s.message_count} msgs)</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="text-xs text-industrial-muted">No detail available.</p>
        )}
      </div>
    </SideDrawer>
  );
}

function UsersSection() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [selectedUser, setSelectedUser] = useState<AdminUserSummary | null>(null);
  const { data, isLoading } = useAdminUsers(page, search);

  const fmtDate = (s: string | null | undefined) =>
    s ? new Date(s).toLocaleDateString() : '—';

  const columns: Column<AdminUserSummary>[] = [
    {
      key: 'email', header: 'Email',
      sortValue: (u) => u.email,
      render: (u) => <span className="text-sm text-industrial">{u.email}</span>,
    },
    {
      key: 'name', header: 'Name', cellClassName: 'hidden md:table-cell',
      sortValue: (u) => `${u.first_name ?? ''} ${u.last_name ?? ''}`.trim().toLowerCase(),
      render: (u) => <span className="text-sm text-industrial-secondary">{u.first_name} {u.last_name}</span>,
    },
    {
      key: 'tier', header: 'Tier', cellClassName: 'hidden md:table-cell',
      sortValue: (u) => u.tier,
      render: (u) => <span className="text-xs text-industrial-muted">{u.tier}</span>,
    },
    {
      key: 'sessions', header: 'Sessions', align: 'right', cellClassName: 'hidden sm:table-cell',
      sortValue: (u) => u.session_count,
      render: (u) => <span className="text-xs text-industrial-muted">{u.session_count}</span>,
    },
    {
      key: 'docs', header: 'Docs', align: 'right', cellClassName: 'hidden sm:table-cell',
      sortValue: (u) => u.document_count,
      render: (u) => <span className="text-xs text-industrial-muted">{u.document_count}</span>,
    },
    {
      key: 'deals', header: 'Deals', align: 'right', cellClassName: 'hidden lg:table-cell',
      sortValue: (u) => u.deal_count,
      render: (u) => <span className="text-xs text-industrial-muted">{u.deal_count}</span>,
    },
    {
      key: 'joined', header: 'Joined', cellClassName: 'hidden lg:table-cell',
      sortValue: (u) => u.created_at ?? null,
      render: (u) => <span className="text-xs text-industrial-muted">{fmtDate(u.created_at)}</span>,
    },
    {
      key: 'last_active', header: 'Last active', cellClassName: 'hidden lg:table-cell',
      sortValue: (u) => u.last_active ?? null,
      render: (u) => <span className="text-xs text-industrial-muted">{fmtDate(u.last_active)}</span>,
    },
  ];

  return (
    <section className="mb-10">
      <h2 className="text-sm font-bold text-industrial mb-4">Users</h2>
      <div className="relative mb-3 max-w-sm">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-industrial-muted" />
        <input
          type="text"
          placeholder="Search by email..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="w-full pl-8 pr-3 py-2 text-sm rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-subtle)] text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)]"
        />
      </div>

      {isLoading ? (
        <SectionLoader />
      ) : data ? (
        <>
          <DataTable
            columns={columns}
            rows={data.users}
            rowKey={(u) => u.id}
            onRowClick={(u) => setSelectedUser(u)}
            initialSort={{ key: 'email', dir: 'asc' }}
            empty="No users found."
          />

          {data.total > data.page_size && (
            <div className="flex items-center gap-2 mt-3">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1.5 text-xs rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-subtle)] text-industrial-secondary disabled:opacity-40"
              >
                Previous
              </button>
              <span className="text-xs text-industrial-muted">
                Page {data.page} of {Math.ceil(data.total / data.page_size)}
              </span>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={page >= Math.ceil(data.total / data.page_size)}
                className="px-3 py-1.5 text-xs rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-subtle)] text-industrial-secondary disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}
        </>
      ) : null}

      <UserDetailDrawer user={selectedUser} onClose={() => setSelectedUser(null)} />
    </section>
  );
}

function UsageSection() {
  const { data, isLoading } = useAdminUsage();

  if (isLoading) return <SectionLoader />;
  if (!data) return null;

  return (
    <section className="mb-10">
      <h2 className="text-sm font-bold text-industrial mb-4">Token usage — {data.period_label}</h2>
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="p-3 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-subtle)]">
          <p className="text-xs text-industrial-muted">Input tokens</p>
          <p className="text-lg font-bold text-industrial">{data.total_input_tokens.toLocaleString()}</p>
        </div>
        <div className="p-3 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-subtle)]">
          <p className="text-xs text-industrial-muted">Output tokens</p>
          <p className="text-lg font-bold text-industrial">{data.total_output_tokens.toLocaleString()}</p>
        </div>
        <div className="p-3 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-subtle)]">
          <p className="text-xs text-industrial-muted">LLM calls</p>
          <p className="text-lg font-bold text-industrial">{data.total_llm_calls.toLocaleString()}</p>
        </div>
      </div>

      {data.top_consumers.length > 0 && (
        <>
          <p className="text-xs text-industrial-muted mb-2">Top consumers</p>
          <DataTable
            rows={data.top_consumers}
            rowKey={(c) => c.user_id}
            initialSort={{ key: 'total', dir: 'desc' }}
            columns={[
              {
                key: 'email', header: 'Email',
                sortValue: (c) => c.email,
                render: (c) => <span className="text-sm text-industrial">{c.email}</span>,
              },
              {
                key: 'total', header: 'Total tokens', align: 'right',
                sortValue: (c) => c.total_tokens,
                render: (c) => <span className="text-sm text-industrial-secondary">{c.total_tokens.toLocaleString()}</span>,
              },
              {
                key: 'calls', header: 'Calls', align: 'right', cellClassName: 'hidden sm:table-cell',
                sortValue: (c) => c.llm_calls,
                render: (c) => <span className="text-sm text-industrial-muted">{c.llm_calls.toLocaleString()}</span>,
              },
            ]}
          />
        </>
      )}
    </section>
  );
}

function AbuseSection() {
  const { data, isLoading } = useAdminAbuse();

  if (isLoading) return <SectionLoader />;
  if (!data) return null;

  const severityColor: Record<string, string> = {
    high: 'text-[var(--color-error)]',
    medium: 'text-amber-500',
    low: 'text-industrial-muted',
  };

  return (
    <section className="mb-10">
      <h2 className="text-sm font-bold text-industrial mb-4">Abuse flags</h2>
      {data.flags.length === 0 ? (
        <div className="flex items-center gap-2 py-4 text-sm text-[var(--color-success)]">
          <CheckCircle2 size={16} />
          <span>All clear — no flags detected</span>
        </div>
      ) : (
        <div className="space-y-2">
          {data.flags.map((f, i) => (
            <div
              key={`${f.user_id}-${f.reason}-${i}`}
              className="flex items-start gap-3 p-3 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-subtle)]"
            >
              <AlertTriangle size={14} className={severityColor[f.severity] || 'text-industrial-muted'} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-industrial">{f.email}</span>
                  <span className={`text-[11px] font-medium ${severityColor[f.severity] || ''}`}>
                    {f.severity}
                  </span>
                </div>
                <p className="text-xs text-industrial-secondary mt-0.5">{f.reason} — {f.detail}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function SectionLoader() {
  return (
    <div className="flex items-center gap-2 py-6 text-xs text-industrial-muted">
      <Loader2 size={14} className="animate-spin" />
      Loading...
    </div>
  );
}

export function AdminPage() {
  const { user } = useAuthStore();

  if (!user?.is_admin) {
    return <Navigate to="/" replace />;
  }

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="max-w-4xl mx-auto px-4 py-8">
          <div className="flex items-center gap-2 mb-6">
            <Shield size={18} className="text-[var(--accent)]" />
            <h1 className="text-lg font-bold text-industrial">Admin</h1>
          </div>

          <OverviewSection />
          <UsersSection />
          <UsageSection />
          <AbuseSection />
        </div>
      </div>
    </AppLayout>
  );
}
