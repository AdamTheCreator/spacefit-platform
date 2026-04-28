import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check } from 'lucide-react';
import { AppLayout } from '../components/Layout/AppLayout';
import { useAuthStore } from '../stores/authStore';
import { useProjects } from '../hooks/useProjects';
import api from '../lib/axios';
import type { OutreachCampaignListItem } from '../types/outreach';
import { contacts as contactRecords, companies as companyRecords } from './contacts/data';

// ---------- Today / hero ----------

function formatToday(): { eyebrow: string; greeting: string } {
  const now = new Date();
  const weekday = now.toLocaleDateString('en-US', { weekday: 'long' });
  const month = now.toLocaleDateString('en-US', { month: 'long' });
  const day = now.getDate();
  const hour = now.getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  return {
    eyebrow: `${weekday.toUpperCase()} · ${month.toUpperCase()} ${day}`,
    greeting,
  };
}

function relativeTime(daysAgo: number | null | undefined): string {
  if (daysAgo === null || daysAgo === undefined) return '—';
  if (daysAgo <= 0) return 'Today';
  if (daysAgo === 1) return 'Yesterday';
  if (daysAgo < 24) return `${daysAgo}h ago`;
  const days = Math.round(daysAgo / 24);
  if (days < 7) return `${days}d ago`;
  return `${Math.round(days / 7)}w ago`;
}

function hoursSince(iso: string | null): number | null {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  const ms = Date.now() - then;
  return Math.max(0, Math.round(ms / (1000 * 60 * 60)));
}

// ---------- Pipeline strip ----------

// Pipeline stage counts. Mirrors the WorkflowPage mock until a real
// pipeline-stage service exists. Numbers must stay in sync with WorkflowPage.
// TODO: swap for usePipelineSummary() once backend exposes the same buckets.
type PipelineStage = {
  key: string;
  label: string;
  count: number;
  delta: string;
  accent?: boolean;
};

const PIPELINE_STAGES: PipelineStage[] = [
  { key: 'sourced',    label: 'Sourced',     count: 3, delta: '+1 wk' },
  { key: 'screening',  label: 'Screening',   count: 2, delta: 'flat'  },
  { key: 'outreach',   label: 'In outreach', count: 2, delta: '+1 wk', accent: true },
  { key: 'diligence',  label: 'Diligence',   count: 1, delta: 'flat'  },
  { key: 'loi_closed', label: 'LOI / Closed', count: 1, delta: '+1 wk' },
];

function PipelineStrip({ onOpen }: { onOpen: () => void }) {
  const total = PIPELINE_STAGES.reduce((s, c) => s + c.count, 0) || 1;
  return (
    <section>
      <div className="flex items-center justify-between mb-2.5">
        <h3 className="font-display text-[15px] font-semibold text-industrial">Pipeline</h3>
        <button
          onClick={onOpen}
          className="text-xs font-medium text-industrial-secondary hover:text-industrial transition-colors"
        >
          Open workflow →
        </button>
      </div>
      <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl overflow-hidden">
        <div className="flex">
          {PIPELINE_STAGES.map((s) => {
            const flex = Math.max(8, (s.count / total) * 100);
            return (
              <div
                key={s.key}
                className={`flex-1 min-w-0 px-4 py-4 border-r last:border-r-0 border-[var(--border-subtle)] ${
                  s.accent ? 'bg-[#FFF6EE]' : ''
                }`}
                style={{ flexBasis: `${flex}%` }}
              >
                <div
                  className={`text-[10.5px] font-semibold uppercase tracking-[0.1em] ${
                    s.accent ? 'text-[#C25E1F]' : 'text-industrial-secondary'
                  }`}
                >
                  {s.label}
                </div>
                <div
                  className={`font-display font-semibold text-[26px] mt-1 leading-none tracking-tight ${
                    s.accent ? 'text-[#C25E1F]' : 'text-industrial'
                  }`}
                >
                  {s.count}
                </div>
                <div className="text-[11px] text-industrial-secondary mt-1">{s.delta}</div>
                <div className="h-[3px] mt-3 rounded-full overflow-hidden bg-[var(--bg-tertiary)]">
                  <div
                    className={`h-full ${s.accent ? 'bg-[#FF8A3D]' : 'bg-[var(--color-mist)]'}`}
                    style={{ width: `${flex}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// ---------- Today panel ----------

type RowKind = 'follow-up' | 'reply' | 'pipeline' | 'staleness';

interface TodayRow {
  id: string;
  kind: RowKind;
  lead: string;
  sub: string;
  when: string;
  actionLabel: string;
  onAction: () => void;
}

const KIND_TONE: Record<RowKind, { label: string; bg: string; fg: string; dot: string }> = {
  'follow-up': { label: 'FOLLOW-UP', bg: '#FFF0E2', fg: '#C25E1F', dot: '#FF8A3D' },
  reply:       { label: 'REPLY',     bg: '#E3F1E5', fg: '#2F7A3B', dot: '#2F7A3B' },
  pipeline:    { label: 'PIPELINE',  bg: '#E8F0FD', fg: '#3A5BA0', dot: '#3A5BA0' },
  staleness:   { label: 'STALENESS', bg: '#F2F5F9', fg: '#596779', dot: '#A7ADB7' },
};

function KindPill({ kind }: { kind: RowKind }) {
  const t = KIND_TONE[kind];
  return (
    <span
      className="inline-flex items-center justify-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold tracking-[0.08em]"
      style={{
        backgroundColor: t.bg,
        color: t.fg,
        minWidth: 92,
      }}
    >
      <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: t.dot }} />
      {t.label}
    </span>
  );
}

function TodayPanel({
  rows,
  isLoading,
}: {
  rows: TodayRow[];
  isLoading: boolean;
}) {
  return (
    <section className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl overflow-hidden">
      <header className="flex items-start justify-between px-[22px] py-[18px] border-b border-[var(--border-subtle)]">
        <div>
          <h3 className="font-display text-[15px] font-semibold text-industrial">Today</h3>
          <p className="text-[12.5px] text-industrial-secondary mt-0.5">
            {isLoading
              ? 'Loading…'
              : rows.length === 0
                ? 'All clear — nothing waiting on you.'
                : `${rows.length} item${rows.length === 1 ? '' : 's'} need a decision`}
          </p>
        </div>
        <button
          type="button"
          disabled
          className="text-[12px] font-medium text-industrial-muted px-2.5 py-1 rounded-md hover:bg-[var(--bg-tertiary)] transition-colors cursor-not-allowed"
          title="Filtering coming soon"
        >
          Filter
        </button>
      </header>

      {rows.length === 0 ? (
        <div className="px-[22px] py-10 text-center">
          <div className="text-[13px] text-industrial-secondary">
            Inbox-zero. The queue's empty for now.
          </div>
        </div>
      ) : (
        <ul className="divide-y divide-[var(--border-subtle)]">
          {rows.map((r) => (
            <li key={r.id} className="flex items-center gap-3 px-[22px] py-3">
              <KindPill kind={r.kind} />
              <div className="flex-1 min-w-0">
                <div className="text-[14px] font-medium text-industrial truncate">{r.lead}</div>
                <div className="text-[12.5px] text-industrial-secondary truncate">{r.sub}</div>
              </div>
              <span className="text-[12px] text-industrial-muted shrink-0 hidden sm:inline">{r.when}</span>
              <button
                onClick={r.onAction}
                className="text-[12px] font-medium text-industrial border border-[var(--border-strong)] rounded-md px-2.5 py-1 hover:bg-[var(--bg-tertiary)] transition-colors shrink-0"
              >
                {r.actionLabel}
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="flex items-center gap-2 px-[22px] py-3 bg-[var(--bg-cream)] border-t border-[var(--border-subtle)]">
        <span className="w-5 h-5 rounded-full bg-[var(--color-success)]/15 text-[var(--color-success)] flex items-center justify-center">
          <Check size={12} strokeWidth={3} />
        </span>
        <span className="text-[12.5px] text-industrial-secondary">
          That's the queue. Inbox-zero by lunch?
        </span>
      </div>
    </section>
  );
}

// ---------- At a glance tiles ----------

interface GlanceTile {
  label: string;
  value: number | string;
  sub: string;
  tone?: 'warn' | 'good' | 'default';
}

function GlanceTiles({ tiles }: { tiles: GlanceTile[] }) {
  return (
    <div className="space-y-3">
      {tiles.map((t) => {
        const subColor =
          t.tone === 'warn' ? 'text-[#C25E1F]'
          : t.tone === 'good' ? 'text-[#2F7A3B]'
          : 'text-industrial-secondary';
        return (
          <div
            key={t.label}
            className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-[14px] px-[18px] py-[16px]"
          >
            <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-industrial-secondary">
              {t.label}
            </div>
            <div className="font-display font-bold text-[30px] text-industrial mt-1 leading-none tracking-tight">
              {t.value}
            </div>
            <div className={`text-[12px] mt-1.5 ${subColor}`}>{t.sub}</div>
          </div>
        );
      })}
    </div>
  );
}

// ---------- Active projects rail ----------

function ActiveProjectsRail({
  projects,
  onAll,
  onOpen,
}: {
  projects: { id: string; name: string; subtitle: string; status: string; pct: number }[];
  onAll: () => void;
  onOpen: (id: string) => void;
}) {
  return (
    <section>
      <div className="flex items-center justify-between mb-2.5">
        <h3 className="font-display text-[15px] font-semibold text-industrial">Active projects</h3>
        <button
          onClick={onAll}
          className="text-xs font-medium text-industrial-secondary hover:text-industrial transition-colors"
        >
          All projects →
        </button>
      </div>

      {projects.length === 0 ? (
        <div className="bg-[var(--bg-secondary)] border border-dashed border-[var(--border-strong)] rounded-xl p-6 text-center text-[13px] text-industrial-secondary">
          No active projects yet. Start one from the Properties screen.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((p) => (
            <button
              key={p.id}
              onClick={() => onOpen(p.id)}
              className="text-left bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-4 hover:border-[var(--color-neutral-900)] hover:shadow-sm transition-all"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-display text-[15.5px] font-semibold text-industrial truncate">
                    {p.name}
                  </div>
                  <div className="text-[12px] text-industrial-secondary mt-0.5 truncate">
                    {p.subtitle}
                  </div>
                </div>
                <span
                  className={`shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-[10.5px] font-semibold ${
                    p.status === 'Active'
                      ? 'bg-[#E8F0FD] text-[#3A5BA0]'
                      : 'bg-[var(--bg-tertiary)] text-industrial-secondary'
                  }`}
                >
                  {p.status}
                </span>
              </div>
              <div className="flex items-center justify-between mt-4 text-[11px] text-industrial-secondary">
                <span>Pipeline filled</span>
                <span className="font-semibold text-industrial">{p.pct}%</span>
              </div>
              <div className="h-1.5 mt-1.5 rounded-full bg-[var(--bg-tertiary)] overflow-hidden">
                <div
                  className="h-full"
                  style={{
                    width: `${p.pct}%`,
                    background: 'linear-gradient(90deg, var(--orbit), var(--mist))',
                  }}
                />
              </div>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

// ---------- Page ----------

export function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { eyebrow, greeting } = formatToday();
  const firstName = user?.first_name || 'there';

  const { data: projectsData } = useProjects({ page: 1 });

  // Outreach campaigns drive Today + At-a-glance.
  const [campaigns, setCampaigns] = useState<OutreachCampaignListItem[] | null>(null);
  const [campaignsError, setCampaignsError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .get<OutreachCampaignListItem[]>('/outreach/campaigns')
      .then((r) => {
        if (!cancelled) setCampaigns(r.data);
      })
      .catch(() => {
        if (!cancelled) setCampaignsError(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Derive Today rows from campaigns + contacts.
  // TODO: replace with thread-level endpoints once they exist:
  //   GET /outreach/threads?status=follow_up_needed
  //   GET /outreach/threads?status=replied
  const todayRows = useMemo<TodayRow[]>(() => {
    const rows: TodayRow[] = [];

    if (campaigns) {
      const followUps = campaigns
        .filter((c) => c.status === 'sent' && c.sent_count - c.replied_count > 0)
        .slice(0, 3);

      followUps.forEach((c) => {
        rows.push({
          id: `fu-${c.id}`,
          kind: 'follow-up',
          lead: c.name,
          sub: c.property_name
            ? `${c.property_name} · ${c.sent_count - c.replied_count} awaiting reply`
            : `${c.sent_count - c.replied_count} awaiting reply`,
          when: relativeTime(hoursSince(c.sent_at ?? c.created_at)),
          actionLabel: 'Review →',
          onAction: () => navigate('/outreach'),
        });
      });

      const replies = campaigns
        .filter((c) => c.replied_count > 0)
        .sort((a, b) => b.replied_count - a.replied_count)
        .slice(0, 2);

      replies.forEach((c) => {
        rows.push({
          id: `rp-${c.id}`,
          kind: 'reply',
          lead: c.name,
          sub: `${c.replied_count} fresh repl${c.replied_count === 1 ? 'y' : 'ies'}`,
          when: relativeTime(hoursSince(c.sent_at)),
          actionLabel: 'Reply →',
          onAction: () => navigate('/outreach'),
        });
      });
    }

    // Pipeline events for today.
    // TODO: wire up when /deals/calendar is enabled here; mock one event for now.
    rows.push({
      id: 'pe-1',
      kind: 'pipeline',
      lead: 'Harper & Ninth — diligence call',
      sub: '10:30 AM · 4 attendees',
      when: 'Today',
      actionLabel: 'Open →',
      onAction: () => navigate('/projects'),
    });

    // Staleness summary.
    const staleCount = contactRecords.filter(
      (c) => c.verif === 'stale' || c.verif === 'bounced',
    ).length;
    if (staleCount > 0) {
      rows.push({
        id: 'st-summary',
        kind: 'staleness',
        lead: `${staleCount} contacts need re-verification`,
        sub: 'Stale or bounced over the last 30 days',
        when: 'Now',
        actionLabel: 'Open →',
        onAction: () => navigate('/contacts'),
      });
    }

    return rows;
  }, [campaigns, navigate]);

  // At-a-glance counts.
  const glance = useMemo<GlanceTile[]>(() => {
    const followUpsDue = campaigns
      ? campaigns.filter((c) => c.status === 'sent' && c.sent_count - c.replied_count > 0).length
      : 0;
    const repliesWaiting = campaigns
      ? campaigns.reduce((sum, c) => sum + c.replied_count, 0)
      : 0;
    const draftsReady = campaigns ? campaigns.filter((c) => c.status === 'draft').length : 0;
    const expandingBrands = companyRecords.filter((c) => c.is_expanding === true).length;

    return [
      {
        label: 'Follow-ups due',
        value: followUpsDue,
        sub: `across ${campaigns?.length ?? 0} campaign${(campaigns?.length ?? 0) === 1 ? '' : 's'}`,
        tone: 'warn',
      },
      {
        label: 'Replies waiting',
        value: repliesWaiting,
        sub: 'last 48 hours',
        tone: 'good',
      },
      {
        label: 'Drafts ready',
        value: draftsReady,
        sub: 'awaiting your review',
      },
      {
        label: 'Brands expanding',
        value: expandingBrands,
        sub: `of ${companyRecords.length} tracked contacts`,
      },
    ];
  }, [campaigns]);

  // Hero summary sentence.
  const heroSentence = useMemo(() => {
    const fu = glance[0].value as number;
    const rep = glance[1].value as number;
    return `${fu} follow-up${fu === 1 ? '' : 's'} need your eyes, ${rep} fresh repl${rep === 1 ? 'y' : 'ies'}, and Harper & Ninth has a diligence call this morning.`;
  }, [glance]);

  // Top 3 projects by recent activity.
  const projectCards = useMemo(() => {
    const items = projectsData?.items ?? [];
    return [...items]
      .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
      .slice(0, 3)
      .map((p) => {
        const docs = p.document_count ?? 0;
        const sessions = p.session_count ?? 0;
        const pct = Math.min(100, Math.max(8, docs * 14 + sessions * 6));
        return {
          id: p.id,
          name: p.name,
          subtitle: p.property_address || p.description || 'No address yet',
          status: p.is_archived ? 'Archived' : 'Active',
          pct,
        };
      });
  }, [projectsData]);

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="px-8 py-7 grid gap-5 max-w-[1400px]">
          {/* Hero banner — compact */}
          <div className="relative bg-[var(--color-neutral-900)] rounded-[20px] px-7 py-7 overflow-hidden text-white">
            {/* Star sparkles */}
            <div className="absolute w-1 h-1 rounded-full bg-[#A7C7F7] opacity-70" style={{ top: 20, left: 30 }} />
            <div className="absolute w-1 h-1 rounded-full bg-[#E5B85C] opacity-80" style={{ top: 60, left: 90 }} />
            <div className="absolute w-[3px] h-[3px] rounded-full bg-[#A7C7F7] opacity-60" style={{ top: 130, left: 60 }} />
            <div className="absolute w-1 h-1 rounded-full bg-[#A7C7F7] opacity-70" style={{ top: 40, left: 260 }} />
            <div className="absolute w-[3px] h-[3px] rounded-full bg-[#A7C7F7] opacity-50" style={{ top: 90, right: 120 }} />
            <div className="absolute w-1 h-1 rounded-full bg-[#E5B85C] opacity-60" style={{ top: 30, right: 40 }} />

            <div className="relative flex flex-col sm:flex-row items-center gap-6">
              <img
                src="/mascots/goose-planner.webp"
                alt=""
                aria-hidden="true"
                className="w-[120px] h-[120px] object-contain shrink-0 select-none"
                draggable={false}
              />
              <div className="flex-1 text-center sm:text-left">
                <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#E5B85C]">
                  {eyebrow}
                </div>
                <h1 className="font-display text-[26px] sm:text-[28px] text-white mt-1.5 tracking-tight">
                  {greeting}, {firstName}.
                </h1>
                <p className="text-[14px] leading-[1.55] text-white/75 mt-2 max-w-[560px] mx-auto sm:mx-0">
                  {heroSentence}
                </p>
              </div>
              <div className="flex flex-col sm:items-end gap-2 shrink-0">
                <button
                  onClick={() => navigate('/outreach')}
                  className="inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white font-semibold text-sm transition-colors shadow-sm"
                >
                  Review queue
                </button>
                <button
                  onClick={() => navigate('/search')}
                  className="inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium text-white/90 hover:text-white hover:bg-white/10 transition-colors"
                >
                  Find new properties →
                </button>
              </div>
            </div>
          </div>

          {/* Pipeline strip */}
          <PipelineStrip onOpen={() => navigate('/workflow')} />

          {/* Today + At a glance */}
          <div
            className="grid gap-5 items-start"
            style={{ gridTemplateColumns: 'minmax(0, 1.85fr) minmax(220px, 0.9fr)' }}
          >
            <TodayPanel rows={todayRows} isLoading={!campaigns && !campaignsError} />
            <GlanceTiles tiles={glance} />
          </div>

          {/* Active projects */}
          <ActiveProjectsRail
            projects={projectCards}
            onAll={() => navigate('/projects')}
            onOpen={(id) => navigate(`/projects/${id}`)}
          />

          <div className="h-4" />
        </div>
      </div>
    </AppLayout>
  );
}

export default DashboardPage;
