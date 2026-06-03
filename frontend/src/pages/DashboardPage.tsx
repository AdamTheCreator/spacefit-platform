import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, Construction } from 'lucide-react';
import { AppLayout } from '../components/Layout/AppLayout';
import { SetupCards } from '../components/Dashboard/SetupCards';
import { useAuthStore } from '../stores/authStore';
import { useProjects } from '../hooks/useProjects';
import api from '../lib/axios';
import type { OutreachCampaignListItem, OutreachThread } from '../types/outreach';
import type { Project } from '../types/project';

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

function daysSince(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  return Math.floor((Date.now() - then) / (1000 * 60 * 60 * 24));
}

// ---------- Triage panel ----------

type RowKind = 'follow-up' | 'reply';

interface TriageRow {
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

function TriagePanel({
  rows,
  isLoading,
  onSeeAll,
}: {
  rows: TriageRow[];
  isLoading: boolean;
  onSeeAll: () => void;
}) {
  const visibleRows = rows.slice(0, 8);
  return (
    <section className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl overflow-hidden">
      <header className="flex items-start justify-between px-[22px] py-[18px] border-b border-[var(--border-subtle)]">
        <div>
          <h3 className="font-display text-[15px] font-semibold text-industrial">Triage queue</h3>
          <p className="text-[12.5px] text-industrial-secondary mt-0.5">
            {isLoading
              ? 'Loading…'
              : rows.length === 0
                ? 'All clear — nothing waiting on you.'
                : `${rows.length} item${rows.length === 1 ? '' : 's'} need a decision`}
          </p>
        </div>
        {rows.length > visibleRows.length && (
          <button
            type="button"
            onClick={onSeeAll}
            className="text-[12px] font-medium text-industrial-secondary hover:text-industrial px-2.5 py-1 rounded-md hover:bg-[var(--bg-tertiary)] transition-colors"
          >
            See all →
          </button>
        )}
      </header>

      {rows.length === 0 ? (
        <div className="px-[22px] py-10 text-center">
          <div className="text-[13px] text-industrial-secondary">
            Inbox-zero. The queue's empty for now.
          </div>
        </div>
      ) : (
        <ul className="divide-y divide-[var(--border-subtle)]">
          {visibleRows.map((r) => (
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

      {rows.length > 0 && (
        <div className="flex items-center gap-2 px-[22px] py-3 bg-[var(--bg-cream)] border-t border-[var(--border-subtle)]">
          <span className="w-5 h-5 rounded-full bg-[var(--color-success)]/15 text-[var(--color-success)] flex items-center justify-center">
            <Check size={12} strokeWidth={3} />
          </span>
          <span className="text-[12.5px] text-industrial-secondary">
            That's the queue. Inbox-zero by lunch?
          </span>
        </div>
      )}
    </section>
  );
}

// ---------- Project stage ----------

type ProjectStage = 'Drafting' | 'Researching' | 'In outreach' | 'Stalled';

const STAGE_TONE: Record<ProjectStage, { bg: string; fg: string }> = {
  Drafting:      { bg: 'var(--bg-tertiary)', fg: 'var(--color-industrial-secondary, #596779)' },
  Researching:   { bg: '#E8F0FD',            fg: '#3A5BA0' },
  'In outreach': { bg: '#FFF0E2',            fg: '#C25E1F' },
  Stalled:       { bg: '#F2F5F9',            fg: '#A7ADB7' },
};

function getProjectStage(
  project: Project,
  campaigns: OutreachCampaignListItem[] | null,
): ProjectStage {
  const stale = (daysSince(project.updated_at) ?? 0) > 30;
  if (stale) return 'Stalled';

  const projectName = project.name.trim().toLowerCase();
  const hasCampaign = !!campaigns?.some(
    (c) => (c.property_name ?? '').trim().toLowerCase() === projectName,
  );
  if (hasCampaign) return 'In outreach';

  const hasWork = (project.document_count ?? 0) > 0 || (project.session_count ?? 0) > 0;
  if (hasWork) return 'Researching';
  return 'Drafting';
}

function ProjectStageBadge({ stage }: { stage: ProjectStage }) {
  const tone = STAGE_TONE[stage];
  return (
    <span
      className="shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-[10.5px] font-semibold"
      style={{ backgroundColor: tone.bg, color: tone.fg }}
    >
      {stage}
    </span>
  );
}

// ---------- Active projects rail ----------

interface ActiveProjectCard {
  id: string;
  name: string;
  subtitle: string;
  stage: ProjectStage;
  docCount: number;
  sessionCount: number;
  updatedAt: string;
}

function ActiveProjectsRail({
  projects,
  onAll,
  onOpen,
}: {
  projects: ActiveProjectCard[];
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
          {projects.map((p) => {
            const updated = relativeTime(
              hoursSince(p.updatedAt),
            );
            return (
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
                  <ProjectStageBadge stage={p.stage} />
                </div>
                <div className="flex items-center gap-3 mt-4 text-[11.5px] text-industrial-secondary">
                  <span>
                    {p.docCount} doc{p.docCount === 1 ? '' : 's'}
                  </span>
                  <span className="w-1 h-1 rounded-full bg-[var(--border-strong)]" />
                  <span>
                    {p.sessionCount} chat{p.sessionCount === 1 ? '' : 's'}
                  </span>
                  <span className="w-1 h-1 rounded-full bg-[var(--border-strong)]" />
                  <span>Updated {updated}</span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}

// ---------- Pipeline placeholder ----------

function PipelinePlaceholder({ onPreview }: { onPreview: () => void }) {
  return (
    <section>
      <div className="flex items-center justify-between mb-2.5">
        <h3 className="font-display text-[15px] font-semibold text-industrial">Pipeline</h3>
      </div>
      <div className="bg-[var(--bg-secondary)] border border-dashed border-[var(--border-strong)] rounded-xl px-5 py-6 flex items-start gap-4">
        <div className="w-10 h-10 rounded-full bg-[var(--bg-tertiary)] text-industrial-muted flex items-center justify-center shrink-0">
          <Construction size={18} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[13.5px] font-semibold text-industrial">
            Pipeline view — coming soon
          </p>
          <p className="text-[12.5px] text-industrial-secondary mt-1 leading-[1.55]">
            Deal-stage tracking will live here once your projects move past
            initial research. Stages will derive from your outreach and
            diligence activity — no manual updates required.
          </p>
          <button
            type="button"
            onClick={onPreview}
            className="mt-2.5 text-[12px] font-medium text-industrial-secondary hover:text-industrial transition-colors"
          >
            Preview workflow board →
          </button>
        </div>
      </div>
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

  // Outreach campaigns drive the follow-up rows + project stages.
  const [campaigns, setCampaigns] = useState<OutreachCampaignListItem[] | null>(null);
  const [campaignsError, setCampaignsError] = useState(false);

  // Replied threads drive the reply rows (real replies only, no placeholders).
  const [threads, setThreads] = useState<OutreachThread[] | null>(null);

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

  useEffect(() => {
    let cancelled = false;
    const loadThreads = () =>
      api
        .get<OutreachThread[]>('/outreach/threads')
        .then((r) => {
          if (!cancelled) setThreads(r.data);
        })
        .catch(() => {
          // Tolerate failure — the reply rows just stay empty.
          if (!cancelled) setThreads([]);
        });

    // Fire-and-forget reply sync (silent no-op when Gmail isn't connected),
    // then (re)load threads so freshly-detected replies show up.
    api
      .post('/outreach/sync-replies')
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) void loadThreads();
      });

    // Also load immediately so existing replies render without waiting on sync.
    void loadThreads();

    return () => {
      cancelled = true;
    };
  }, []);

  // Derive triage rows from real data only — reply rows come from detected
  // threads (GET /outreach/threads), follow-up rows from campaign stats.
  const triageRows = useMemo<TriageRow[]>(() => {
    const rows: TriageRow[] = [];

    // Replies come first — they're the freshest signal a human needs to see.
    // Backend already orders threads by received/replied time, newest first.
    (threads ?? []).forEach((t) => {
      rows.push({
        id: `rp-${t.id}`,
        kind: 'reply',
        lead: t.campaign_name,
        sub: `${t.tenant_name} · ${t.snippet || 'replied'}`,
        when: relativeTime(hoursSince(t.received_at)),
        actionLabel: 'Reply →',
        onAction: () => navigate('/outreach'),
      });
    });

    const followUps = (campaigns ?? []).filter(
      (c) => c.status === 'sent' && c.sent_count - c.replied_count > 0,
    );

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

    return rows;
  }, [threads, campaigns, navigate]);

  // Real counts feed the hero one-liner — no mock data, no placeholder events.
  const heroSummary = useMemo(() => {
    if (!campaigns) return null;
    const replies = campaigns.reduce((sum, c) => sum + c.replied_count, 0);
    const followUps = campaigns.filter(
      (c) => c.status === 'sent' && c.sent_count - c.replied_count > 0,
    ).length;
    if (replies === 0 && followUps === 0) {
      return 'All caught up — nothing waiting on you.';
    }
    const repliesPart =
      replies === 0 ? '' : `${replies} repl${replies === 1 ? 'y' : 'ies'} waiting`;
    const followUpsPart =
      followUps === 0
        ? ''
        : `${followUps} follow-up${followUps === 1 ? '' : 's'} due`;
    return [repliesPart, followUpsPart].filter(Boolean).join(' · ');
  }, [campaigns]);

  // Top 6 projects by recent activity, with derived stage badges.
  const projectCards = useMemo<ActiveProjectCard[]>(() => {
    const items = projectsData?.items ?? [];
    return [...items]
      .filter((p) => !p.is_archived)
      .sort(
        (a, b) =>
          new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
      )
      .slice(0, 6)
      .map((p) => ({
        id: p.id,
        name: p.name,
        subtitle: p.property_address || p.description || 'No address yet',
        stage: getProjectStage(p, campaigns),
        docCount: p.document_count ?? 0,
        sessionCount: p.session_count ?? 0,
        updatedAt: p.updated_at,
      }));
  }, [projectsData, campaigns]);

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="px-8 py-7 grid gap-5 max-w-[1400px]">
          {/* Hero banner — compact, single CTA, no mock content */}
          <div className="relative bg-[var(--color-neutral-900)] rounded-[20px] px-7 py-7 overflow-hidden text-white">
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
                  {heroSummary ?? 'Loading your queue…'}
                </p>
              </div>
              <div className="shrink-0">
                <button
                  onClick={() => navigate('/outreach')}
                  className="inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white font-semibold text-sm transition-colors shadow-sm"
                >
                  Review outreach queue
                </button>
              </div>
            </div>
          </div>

          {/* Triage queue — primary action */}
          <TriagePanel
            rows={triageRows}
            isLoading={!campaigns && !campaignsError}
            onSeeAll={() => navigate('/outreach')}
          />

          {/* Active projects */}
          <ActiveProjectsRail
            projects={projectCards}
            onAll={() => navigate('/projects')}
            onOpen={(id) => navigate(`/projects/${id}`)}
          />

          {/* Pipeline — placeholder until backend has real stage data */}
          <PipelinePlaceholder onPreview={() => navigate('/workflow')} />

          {/* Setup cards — one-time tasks live at the bottom */}
          <SetupCards />

          <div className="h-4" />
        </div>
      </div>
    </AppLayout>
  );
}

export default DashboardPage;
