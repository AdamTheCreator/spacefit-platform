import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Mail,
  Send,
  Eye,
  MessageCircle,
  AlertCircle,
  Plus,
  MoreVertical,
  Search,
} from 'lucide-react';
import { AppLayout } from '../components/Layout';
import { EmailComposer } from '../components/Outreach';
import api from '../lib/axios';
import type {
  OutreachCampaignListItem,
  OutreachCampaign,
  CampaignStatus,
} from '../types/outreach';

// Status badge colors - industrial design
const STATUS_COLORS: Record<CampaignStatus, { bg: string; text: string }> = {
  draft: { bg: 'bg-[var(--bg-tertiary)] border border-industrial-subtle', text: 'text-industrial-secondary' },
  scheduled: { bg: 'bg-[var(--accent)]/10 border border-[var(--accent)]/30', text: 'text-[var(--accent)]' },
  sending: { bg: 'bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30', text: 'text-[var(--color-warning)]' },
  sent: { bg: 'bg-[var(--color-success)]/10 border border-[var(--color-success)]/30', text: 'text-[var(--color-success)]' },
  cancelled: { bg: 'bg-[var(--color-error)]/10 border border-[var(--color-error)]/30', text: 'text-[var(--color-error)]' },
};

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function calculateOpenRate(campaign: OutreachCampaignListItem): number {
  if (campaign.sent_count === 0) return 0;
  return Math.round((campaign.opened_count / campaign.sent_count) * 100);
}

export function OutreachPage() {
  const [campaigns, setCampaigns] = useState<OutreachCampaignListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<CampaignStatus | 'all'>('all');
  const [_selectedCampaign, _setSelectedCampaign] = useState<OutreachCampaign | null>(null);
  const [showComposer, setShowComposer] = useState(false);

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

  // Fetch campaigns on mount
  useEffect(() => {
    fetchCampaigns();
  }, []);

  // Filter campaigns
  const filteredCampaigns = campaigns.filter((campaign) => {
    const matchesSearch =
      campaign.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      campaign.property_name?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || campaign.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  // Stats summary
  const stats = {
    total: campaigns.length,
    sent: campaigns.filter((c) => c.status === 'sent').length,
    totalEmails: campaigns.reduce((sum, c) => sum + c.sent_count, 0),
    totalOpens: campaigns.reduce((sum, c) => sum + c.opened_count, 0),
    totalReplies: campaigns.reduce((sum, c) => sum + c.replied_count, 0),
  };

  const avgOpenRate = stats.totalEmails > 0
    ? Math.round((stats.totalOpens / stats.totalEmails) * 100)
    : 0;

  return (
    <AppLayout>
      <div className="h-full flex flex-col overflow-hidden bg-industrial">
        {/* Header */}
        <div className="flex-shrink-0 px-6 py-4 border-b border-industrial bg-[var(--bg-elevated)]">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="font-mono text-lg font-bold tracking-tight text-industrial flex items-center gap-2">
                <Mail className="w-5 h-5 text-[var(--accent)]" />
                Outreach Campaigns
              </h1>
              <p className="font-mono text-xs text-industrial-muted mt-1">
                Email campaigns created from tenant gap analysis results
              </p>
            </div>

            <button
              onClick={() => setShowComposer(true)}
              className="btn-industrial-primary"
            >
              <Plus className="w-4 h-4" />
              New Campaign
            </button>
          </div>

          {/* Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
            <div className="bg-[var(--bg-tertiary)] p-4 border border-industrial-subtle">
              <div className="font-mono text-2xl font-bold text-industrial">{stats.total}</div>
              <div className="label-technical">Total Campaigns</div>
            </div>
            <div className="bg-[var(--bg-tertiary)] p-4 border border-industrial-subtle">
              <div className="font-mono text-2xl font-bold text-[var(--color-success)]">{stats.totalEmails}</div>
              <div className="label-technical">Emails Sent</div>
            </div>
            <div className="bg-[var(--bg-tertiary)] p-4 border border-industrial-subtle">
              <div className="font-mono text-2xl font-bold text-[var(--accent)]">{stats.totalOpens}</div>
              <div className="label-technical">Opens</div>
            </div>
            <div className="bg-[var(--bg-tertiary)] p-4 border border-industrial-subtle">
              <div className="font-mono text-2xl font-bold text-industrial">{avgOpenRate}%</div>
              <div className="label-technical">Avg Open Rate</div>
            </div>
            <div className="bg-[var(--bg-tertiary)] p-4 border border-industrial-subtle">
              <div className="font-mono text-2xl font-bold text-[var(--color-warning)]">{stats.totalReplies}</div>
              <div className="label-technical">Replies</div>
            </div>
          </div>

          {/* Search & Filters */}
          <div className="flex items-center gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-industrial-muted" />
              <input
                type="text"
                placeholder="Search campaigns…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input-industrial pl-10 w-full"
              />
            </div>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as CampaignStatus | 'all')}
              className="input-industrial"
            >
              <option value="all">All Status</option>
              <option value="draft">Draft</option>
              <option value="sent">Sent</option>
              <option value="sending">Sending</option>
              <option value="scheduled">Scheduled</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
        </div>

        {/* Campaign List */}
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <div className="flex items-center gap-3">
                <div className="relative w-5 h-5">
                  <div className="w-5 h-5 border border-industrial" />
                  <div className="absolute inset-0 border-t border-[var(--accent)] animate-spin" />
                </div>
                <span className="label-technical">Loading campaigns...</span>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-center">
                <AlertCircle className="w-12 h-12 text-[var(--color-error)] mx-auto mb-3" />
                <p className="font-mono text-xs text-[var(--color-error)]">{error}</p>
              </div>
            </div>
          ) : filteredCampaigns.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-center">
              <div className="w-16 h-16 bg-[var(--bg-tertiary)] border border-industrial-subtle flex items-center justify-center mx-auto mb-4">
                <Mail className="w-8 h-8 text-industrial-muted" />
              </div>
              <h3 className="font-mono text-sm font-semibold uppercase tracking-wide text-industrial mb-2">No campaigns yet</h3>
              <p className="font-mono text-xs text-industrial-muted mb-6 max-w-md">
                Create your first outreach campaign from a tenant gap analysis. Ask SpaceFit to
                find tenant gaps and then reach out to the identified tenants.
              </p>
              <Link
                to="/chat"
                className="btn-industrial-primary"
              >
                <Plus className="w-4 h-4" />
                Find Tenant Gaps
              </Link>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredCampaigns.map((campaign) => (
                <div
                  key={campaign.id}
                  className="card-industrial hover:border-industrial cursor-pointer transition-colors"
                  onClick={() => {
                    // TODO: Open campaign detail modal
                  }}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-1">
                        <h3 className="font-mono text-sm font-medium text-industrial truncate">
                          {campaign.name}
                        </h3>
                        <span
                          className={`px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide
                            ${STATUS_COLORS[campaign.status].bg}
                            ${STATUS_COLORS[campaign.status].text}`}
                        >
                          {campaign.status}
                        </span>
                      </div>
                      <p className="font-mono text-xs text-industrial-muted truncate">
                        {campaign.property_name || 'No property name'}
                      </p>
                      <p className="font-mono text-[10px] text-industrial-muted mt-1">
                        Created {formatDate(campaign.created_at)}
                        {campaign.sent_at && ` • Sent ${formatDate(campaign.sent_at)}`}
                      </p>
                    </div>

                    {/* Stats */}
                    <div className="flex items-center gap-6 ml-4">
                      <div className="text-center">
                        <div className="flex items-center gap-1 text-industrial-muted">
                          <Send className="w-4 h-4" />
                          <span className="font-mono text-lg font-semibold text-industrial">
                            {campaign.sent_count}
                          </span>
                        </div>
                        <div className="label-technical">Sent</div>
                      </div>

                      <div className="text-center">
                        <div className="flex items-center gap-1 text-industrial-muted">
                          <Eye className="w-4 h-4" />
                          <span className="font-mono text-lg font-semibold text-industrial">
                            {campaign.opened_count}
                          </span>
                        </div>
                        <div className="label-technical">
                          Opened ({calculateOpenRate(campaign)}%)
                        </div>
                      </div>

                      <div className="text-center">
                        <div className="flex items-center gap-1 text-industrial-muted">
                          <MessageCircle className="w-4 h-4" />
                          <span className="font-mono text-lg font-semibold text-industrial">
                            {campaign.replied_count}
                          </span>
                        </div>
                        <div className="label-technical">Replied</div>
                      </div>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          // TODO: Open actions menu
                        }}
                        className="p-2 text-industrial-muted hover:text-industrial hover:bg-[var(--bg-secondary)]
                                   transition-colors"
                      >
                        <MoreVertical className="w-5 h-5" />
                      </button>
                    </div>
                  </div>

                  {/* Progress bar for sent campaigns */}
                  {campaign.status === 'sent' && campaign.sent_count > 0 && (
                    <div className="mt-3 pt-3 border-t border-industrial-subtle">
                      <div className="flex items-center gap-2 label-technical mb-1">
                        <span>Open rate</span>
                        <span className="text-industrial font-medium">
                          {calculateOpenRate(campaign)}%
                        </span>
                      </div>
                      <div className="h-1 bg-[var(--bg-tertiary)] overflow-hidden">
                        <div
                          className="h-full bg-[var(--accent)] transition-all"
                          style={{ width: `${calculateOpenRate(campaign)}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
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
              onClose={() => setShowComposer(false)}
              onCampaignCreated={() => {
                setShowComposer(false);
                fetchCampaigns();
              }}
            />
          </div>
        </div>
      )}
    </AppLayout>
  );
}
