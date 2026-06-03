import { useState, useEffect, useMemo } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  Mail,
  MapPin,
  Send,
  Eye,
  MessageCircle,
  AlertCircle,
  Plus,
  Search,
  BarChart2,
  Users,
  ChevronRight,
} from 'lucide-react';
import { AppLayout } from '../components/Layout';
import { EmailComposer, CampaignDetail } from '../components/Outreach';
import api from '../lib/axios';
import type {
  OutreachCampaignListItem,
  OutreachCampaign,
  CampaignStatus,
  CreateRecipientRequest,
} from '../types/outreach';

type FilterLabel = 'All' | 'Drafting' | 'Active' | 'Complete' | 'Paused';

const FILTER_TO_STATUSES: Record<FilterLabel, CampaignStatus[]> = {
  All: [],
  Drafting: ['draft'],
  Active: ['scheduled', 'sending'],
  Complete: ['sent'],
  Paused: ['cancelled'],
};

const STATUS_PILL: Record<CampaignStatus, { label: string; bg: string; text: string }> = {
  draft:     { label: 'Drafting',  bg: 'bg-[var(--bg-tertiary)]',              text: 'text-[var(--text-secondary)]' },
  scheduled: { label: 'Scheduled', bg: 'bg-[var(--orbit)]/10',                 text: 'text-[var(--orbit)]' },
  sending:   { label: 'Active',    bg: 'bg-[var(--accent)]/10',                text: 'text-[var(--accent)]' },
  sent:      { label: 'Complete',  bg: 'bg-[var(--color-success)]/10',         text: 'text-[var(--color-success)]' },
  cancelled: { label: 'Paused',    bg: 'bg-[var(--color-warning)]/10',         text: 'text-[var(--color-warning)]' },
};

function openRate(c: OutreachCampaignListItem): number {
  return c.sent_count > 0 ? Math.round((c.opened_count / c.sent_count) * 100) : 0;
}

function replyRate(c: OutreachCampaignListItem): number {
  return c.sent_count > 0 ? Math.round((c.replied_count / c.sent_count) * 100) : 0;
}

function fmtDate(dateStr: string | null): string {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

// ─── Campaign Card ────────────────────────────────────────────────────────────
function CampaignCard({
  campaign,
  onClick,
}: {
  campaign: OutreachCampaignListItem;
  onClick: () => void;
}) {
  const pill = STATUS_PILL[campaign.status];
  const open = openRate(campaign);
  const reply = replyRate(campaign);
  const isSent = campaign.status === 'sent';

  return (
    <button
      onClick={onClick}
      className="group text-left w-full rounded-[var(--radius-lg)] bg-[var(--bg-secondary)] border border-[var(--border-subtle)]
                 shadow-[var(--shadow-sm)] hover:shadow-[var(--shadow-md)] hover:border-[var(--border-default)]
                 transition-all duration-150 overflow-hidden"
    >
      {/* Card top accent bar */}
      <div className={`h-1 w-full ${isSent ? 'bg-[var(--color-success)]' : campaign.status === 'sending' ? 'bg-[var(--accent)]' : 'bg-[var(--border-subtle)]'}`} />

      <div className="p-5">
        {/* Header row */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide
                             ${pill.bg} ${pill.text}`}
              >
                {pill.label}
              </span>
            </div>
            <h3
              className="text-sm font-semibold truncate"
              style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}
            >
              {campaign.name}
            </h3>
            {campaign.property_name && (
              <p className="flex items-center gap-1 mt-1 text-[11px]" style={{ color: 'var(--text-muted)' }}>
                <MapPin className="w-3 h-3 flex-shrink-0" />
                <span className="truncate">{campaign.property_name}</span>
              </p>
            )}
          </div>
          <ChevronRight className="w-4 h-4 flex-shrink-0 mt-1 opacity-0 group-hover:opacity-100 transition-opacity"
            style={{ color: 'var(--text-muted)' }} />
        </div>

        {/* Progress bar (sent/sending only) */}
        {(isSent || campaign.status === 'sending') && campaign.total_recipients > 0 && (
          <div className="mb-4">
            <div className="flex justify-between text-[10px] mb-1" style={{ color: 'var(--text-muted)' }}>
              <span>Delivery</span>
              <span>{campaign.sent_count}/{campaign.total_recipients} sent</span>
            </div>
            <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-tertiary)' }}>
              {/* sent segment */}
              <div className="h-full flex">
                <div
                  className="h-full"
                  style={{
                    width: `${Math.round((campaign.opened_count / campaign.total_recipients) * 100)}%`,
                    background: 'var(--color-success)',
                  }}
                />
                <div
                  className="h-full"
                  style={{
                    width: `${Math.round(((campaign.sent_count - campaign.opened_count) / campaign.total_recipients) * 100)}%`,
                    background: 'var(--orbit)',
                    opacity: 0.35,
                  }}
                />
              </div>
            </div>
            <div className="flex gap-3 mt-1.5 text-[10px]" style={{ color: 'var(--text-muted)' }}>
              <span className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: 'var(--color-success)' }} />
                {campaign.opened_count} opened
              </span>
              <span className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: 'var(--orbit)', opacity: 0.5 }} />
                {campaign.sent_count - campaign.opened_count} delivered
              </span>
            </div>
          </div>
        )}

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-2 border-t pt-3" style={{ borderColor: 'var(--border-subtle)' }}>
          <div className="text-center">
            <div className="flex items-center justify-center gap-1 mb-0.5">
              <Send className="w-3 h-3" style={{ color: 'var(--text-muted)' }} />
              <span className="text-sm font-bold" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                {campaign.sent_count}
              </span>
            </div>
            <div className="text-[10px] uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>Sent</div>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center gap-1 mb-0.5">
              <Eye className="w-3 h-3" style={{ color: 'var(--text-muted)' }} />
              <span className="text-sm font-bold" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                {open}%
              </span>
            </div>
            <div className="text-[10px] uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>Open rate</div>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center gap-1 mb-0.5">
              <MessageCircle className="w-3 h-3" style={{ color: 'var(--text-muted)' }} />
              <span className="text-sm font-bold" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                {reply}%
              </span>
            </div>
            <div className="text-[10px] uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>Reply rate</div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-3 pt-2 border-t flex items-center justify-between" style={{ borderColor: 'var(--border-subtle)' }}>
          <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
            {campaign.sent_at ? `Sent ${fmtDate(campaign.sent_at)}` : `Created ${fmtDate(campaign.created_at)}`}
          </span>
          <span
            className="text-[11px] font-medium"
            style={{ color: 'var(--accent)', fontFamily: 'var(--font-display)' }}
          >
            View details →
          </span>
        </div>
      </div>
    </button>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export function OutreachPage() {
  const [campaigns, setCampaigns] = useState<OutreachCampaignListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState<FilterLabel>('All');
  const [sortBy, setSortBy] = useState<'newest' | 'oldest' | 'name'>('newest');
  const [selectedCampaign, setSelectedCampaign] = useState<OutreachCampaign | null>(null);
  const [showComposer, setShowComposer] = useState(false);
  const [composeRecipients, setComposeRecipients] = useState<CreateRecipientRequest[]>([]);
  const location = useLocation();
  const navigate = useNavigate();

  const fetchCampaigns = async () => {
    try {
      setIsLoading(true);
      const response = await api.get<OutreachCampaignListItem[]>('/outreach/campaigns');
      setCampaigns(response.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load campaigns');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCampaigns();
  }, []);

  useEffect(() => {
    const state = location.state as { composeRecipients?: CreateRecipientRequest[] } | null;
    if (state?.composeRecipients?.length) {
      setComposeRecipients(state.composeRecipients);
      setShowComposer(true);
      navigate(location.pathname, { replace: true, state: null });
    }
  }, [location, navigate]);

  // Metrics
  const metrics = useMemo(() => {
    const active = campaigns.filter((c) => c.status === 'scheduled' || c.status === 'sending').length;
    const totalSent = campaigns.reduce((s, c) => s + c.sent_count, 0);
    const totalReplied = campaigns.reduce((s, c) => s + c.replied_count, 0);
    const avgReply = totalSent > 0 ? Math.round((totalReplied / totalSent) * 100) : 0;
    return { active, totalSent, avgReply, totalReplied };
  }, [campaigns]);

  // Filtered + sorted campaigns
  const filteredCampaigns = useMemo(() => {
    const statuses = FILTER_TO_STATUSES[activeFilter];
    let list = campaigns.filter((c) => {
      const matchStatus = statuses.length === 0 || statuses.includes(c.status);
      const q = searchQuery.toLowerCase();
      const matchSearch =
        !q ||
        c.name.toLowerCase().includes(q) ||
        (c.property_name?.toLowerCase().includes(q) ?? false);
      return matchStatus && matchSearch;
    });

    if (sortBy === 'newest') list = [...list].sort((a, b) => b.created_at.localeCompare(a.created_at));
    if (sortBy === 'oldest') list = [...list].sort((a, b) => a.created_at.localeCompare(b.created_at));
    if (sortBy === 'name') list = [...list].sort((a, b) => a.name.localeCompare(b.name));

    return list;
  }, [campaigns, activeFilter, searchQuery, sortBy]);

  const FILTERS: FilterLabel[] = ['All', 'Drafting', 'Active', 'Complete', 'Paused'];

  return (
    <AppLayout>
      <div className="h-full flex flex-col overflow-hidden" style={{ background: 'var(--bg-primary)' }}>
        {/* ── Header ── */}
        <div
          className="flex-shrink-0 px-6 py-5 border-b"
          style={{ background: 'var(--bg-secondary)', borderColor: 'var(--border-subtle)' }}
        >
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-3">
              <div
                className="w-9 h-9 rounded-[var(--radius-md)] flex items-center justify-center"
                style={{ background: 'var(--accent)/10' }}
              >
                <Mail className="w-5 h-5" style={{ color: 'var(--accent)' }} />
              </div>
              <div>
                <h1
                  className="text-lg font-bold leading-tight"
                  style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}
                >
                  Outreach
                </h1>
                <p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                  Drafts go out, replies come in — you stay in the driver's seat.
                </p>
              </div>
            </div>
            <button onClick={() => setShowComposer(true)} className="btn-industrial-primary">
              <Plus className="w-4 h-4" />
              New Campaign
            </button>
          </div>

          {/* Metrics Strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
            {[
              { label: 'Active campaigns', value: metrics.active, icon: <BarChart2 className="w-4 h-4" />, accent: 'var(--accent)' },
              { label: 'Contacts reached', value: metrics.totalSent, icon: <Users className="w-4 h-4" />, accent: 'var(--orbit)' },
              { label: 'Reply rate', value: `${metrics.avgReply}%`, icon: <MessageCircle className="w-4 h-4" />, accent: 'var(--color-success)' },
              { label: 'Total replies', value: metrics.totalReplied, icon: <Mail className="w-4 h-4" />, accent: 'var(--mist)' },
            ].map(({ label, value, icon, accent }) => (
              <div
                key={label}
                className="rounded-[var(--radius-md)] p-4"
                style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)' }}
              >
                <div className="flex items-center gap-2 mb-2" style={{ color: accent }}>
                  {icon}
                  <span className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--text-muted)' }}>
                    {label}
                  </span>
                </div>
                <div
                  className="text-2xl font-bold"
                  style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}
                >
                  {value}
                </div>
              </div>
            ))}
          </div>

          {/* Controls */}
          <div className="flex items-center gap-3">
            <div className="relative flex-1 max-w-xs">
              <Search
                className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5"
                style={{ color: 'var(--text-muted)' }}
              />
              <input
                type="text"
                placeholder="Search campaigns…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input-industrial pl-9 w-full text-sm"
              />
            </div>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
              className="input-industrial text-sm"
            >
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="name">Name A–Z</option>
            </select>
          </div>

          {/* Filter Chips */}
          <div className="flex items-center gap-2 mt-3">
            {FILTERS.map((f) => {
              const count =
                f === 'All'
                  ? campaigns.length
                  : campaigns.filter((c) => FILTER_TO_STATUSES[f].includes(c.status)).length;
              const isActive = activeFilter === f;
              return (
                <button
                  key={f}
                  onClick={() => setActiveFilter(f)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-150"
                  style={{
                    fontFamily: 'var(--font-body)',
                    background: isActive ? 'var(--accent)' : 'var(--bg-tertiary)',
                    color: isActive ? '#fff' : 'var(--text-secondary)',
                    border: `1px solid ${isActive ? 'var(--accent)' : 'var(--border-subtle)'}`,
                  }}
                >
                  {f}
                  <span
                    className="text-[10px] font-bold tabular-nums"
                    style={{ opacity: isActive ? 0.85 : 0.6 }}
                  >
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* ── Campaign Grid ── */}
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <div className="flex items-center gap-3">
                <div className="relative w-5 h-5">
                  <div className="w-5 h-5 border border-[var(--border-default)] rounded-sm" />
                  <div className="absolute inset-0 border-t border-[var(--accent)] rounded-sm animate-spin" />
                </div>
                <span className="text-sm" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)' }}>
                  Loading campaigns…
                </span>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-center">
                <AlertCircle className="w-10 h-10 mx-auto mb-3" style={{ color: 'var(--color-error)' }} />
                <p className="text-sm" style={{ color: 'var(--color-error)', fontFamily: 'var(--font-mono)' }}>{error}</p>
              </div>
            </div>
          ) : filteredCampaigns.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <img
                src="/mascots/goose-launch.webp"
                alt=""
                aria-hidden="true"
                className="w-32 h-32 mx-auto mb-4 object-contain select-none"
                draggable={false}
              />
              <h3
                className="text-base font-semibold mb-2"
                style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}
              >
                {activeFilter === 'All' ? 'Ready for launch' : `No ${activeFilter.toLowerCase()} campaigns`}
              </h3>
              <p
                className="text-sm mb-6 max-w-sm"
                style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)' }}
              >
                {activeFilter === 'All'
                  ? 'Create your first outreach campaign from a tenant gap analysis. Ask Space Goose to find tenant gaps and reach out to identified tenants.'
                  : 'Try selecting a different filter or create a new campaign.'}
              </p>
              {activeFilter === 'All' ? (
                <Link to="/chat" className="btn-industrial-primary">
                  <Plus className="w-4 h-4" />
                  Find Tenant Gaps
                </Link>
              ) : (
                <button onClick={() => setActiveFilter('All')} className="btn-industrial-primary">
                  View all campaigns
                </button>
              )}
            </div>
          ) : (
            <div
              className="grid gap-4"
              style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))' }}
            >
              {filteredCampaigns.map((campaign) => (
                <CampaignCard
                  key={campaign.id}
                  campaign={campaign}
                  onClick={async () => {
                    try {
                      const response = await api.get<OutreachCampaign>(`/outreach/campaigns/${campaign.id}`);
                      setSelectedCampaign(response.data);
                    } catch (err) {
                      console.error('Failed to load campaign:', err);
                    }
                  }}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Email Composer Overlay */}
      {showComposer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setShowComposer(false)}
          />
          <div className="relative w-full max-w-3xl mx-4">
            <EmailComposer
              initialRecipients={composeRecipients}
              onClose={() => {
                setShowComposer(false);
                setComposeRecipients([]);
              }}
              onCampaignCreated={() => {
                setShowComposer(false);
                setComposeRecipients([]);
                fetchCampaigns();
              }}
            />
          </div>
        </div>
      )}

      {/* Campaign Detail Modal */}
      {selectedCampaign && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setSelectedCampaign(null)}
          />
          <div className="relative w-full max-w-4xl mx-4 max-h-[90vh] overflow-y-auto">
            <CampaignDetail
              campaign={selectedCampaign}
              onClose={() => {
                setSelectedCampaign(null);
                fetchCampaigns();
              }}
            />
          </div>
        </div>
      )}
    </AppLayout>
  );
}
