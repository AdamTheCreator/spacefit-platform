import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import {
  Users,
  Activity,
  FileText,
  FolderOpen,
  Kanban,
  Search,
  ChevronDown,
  ChevronUp,
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

function UserRow({ user, isExpanded, onToggle }: { user: AdminUserSummary; isExpanded: boolean; onToggle: () => void }) {
  const { data: detail, isLoading } = useAdminUserDetail(isExpanded ? user.id : null);

  return (
    <>
      <tr
        onClick={onToggle}
        className="cursor-pointer hover:bg-[var(--bg-tertiary)] transition-colors border-b border-[var(--border-subtle)]"
      >
        <td className="py-2.5 px-3 text-sm text-industrial">{user.email}</td>
        <td className="py-2.5 px-3 text-sm text-industrial-secondary hidden md:table-cell">
          {user.first_name} {user.last_name}
        </td>
        <td className="py-2.5 px-3 text-xs text-industrial-muted hidden md:table-cell">{user.tier}</td>
        <td className="py-2.5 px-3 text-xs text-industrial-muted text-right hidden sm:table-cell">{user.session_count}</td>
        <td className="py-2.5 px-3 text-xs text-industrial-muted text-right hidden sm:table-cell">{user.document_count}</td>
        <td className="py-2.5 px-3 text-xs text-industrial-muted text-right hidden lg:table-cell">{user.deal_count}</td>
        <td className="py-2.5 px-3 text-xs text-industrial-muted hidden lg:table-cell">
          {user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
        </td>
        <td className="py-2.5 px-3 text-xs text-industrial-muted hidden lg:table-cell">
          {user.last_active ? new Date(user.last_active).toLocaleDateString() : '—'}
        </td>
        <td className="py-2.5 px-3 w-8">
          {isExpanded ? <ChevronUp size={14} className="text-industrial-muted" /> : <ChevronDown size={14} className="text-industrial-muted" />}
        </td>
      </tr>
      {isExpanded && (
        <tr>
          <td colSpan={9} className="bg-[var(--bg-secondary)] px-4 py-3">
            {isLoading ? (
              <div className="flex items-center gap-2 text-xs text-industrial-muted py-2">
                <Loader2 size={12} className="animate-spin" /> Loading...
              </div>
            ) : detail ? (
              <div className="space-y-3">
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
            ) : null}
          </td>
        </tr>
      )}
    </>
  );
}

function UsersSection() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const { data, isLoading } = useAdminUsers(page, search);

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
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[var(--border-subtle)]">
                  <th className="py-2 px-3 text-left text-[11px] text-industrial-muted font-medium">Email</th>
                  <th className="py-2 px-3 text-left text-[11px] text-industrial-muted font-medium hidden md:table-cell">Name</th>
                  <th className="py-2 px-3 text-left text-[11px] text-industrial-muted font-medium hidden md:table-cell">Tier</th>
                  <th className="py-2 px-3 text-right text-[11px] text-industrial-muted font-medium hidden sm:table-cell">Sessions</th>
                  <th className="py-2 px-3 text-right text-[11px] text-industrial-muted font-medium hidden sm:table-cell">Docs</th>
                  <th className="py-2 px-3 text-right text-[11px] text-industrial-muted font-medium hidden lg:table-cell">Deals</th>
                  <th className="py-2 px-3 text-left text-[11px] text-industrial-muted font-medium hidden lg:table-cell">Joined</th>
                  <th className="py-2 px-3 text-left text-[11px] text-industrial-muted font-medium hidden lg:table-cell">Last active</th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody>
                {data.users.map((u) => (
                  <UserRow
                    key={u.id}
                    user={u}
                    isExpanded={expandedId === u.id}
                    onToggle={() => setExpandedId(expandedId === u.id ? null : u.id)}
                  />
                ))}
              </tbody>
            </table>
          </div>

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
          <table className="w-full">
            <thead>
              <tr className="border-b border-[var(--border-subtle)]">
                <th className="py-2 px-3 text-left text-[11px] text-industrial-muted font-medium">Email</th>
                <th className="py-2 px-3 text-right text-[11px] text-industrial-muted font-medium">Total tokens</th>
                <th className="py-2 px-3 text-right text-[11px] text-industrial-muted font-medium hidden sm:table-cell">Calls</th>
              </tr>
            </thead>
            <tbody>
              {data.top_consumers.map((c) => (
                <tr key={c.user_id} className="border-b border-[var(--border-subtle)]">
                  <td className="py-2 px-3 text-sm text-industrial">{c.email}</td>
                  <td className="py-2 px-3 text-sm text-industrial-secondary text-right">{c.total_tokens.toLocaleString()}</td>
                  <td className="py-2 px-3 text-sm text-industrial-muted text-right hidden sm:table-cell">{c.llm_calls.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
