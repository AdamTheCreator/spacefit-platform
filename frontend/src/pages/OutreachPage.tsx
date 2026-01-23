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
import api from '../lib/axios';
import type {
  OutreachCampaignListItem,
  OutreachCampaign,
  CampaignStatus,
} from '../types/outreach';

// Status badge colors
const STATUS_COLORS: Record<CampaignStatus, { bg: string; text: string }> = {
  draft: { bg: 'bg-gray-700', text: 'text-gray-300' },
  scheduled: { bg: 'bg-blue-900/50', text: 'text-blue-300' },
  sending: { bg: 'bg-yellow-900/50', text: 'text-yellow-300' },
  sent: { bg: 'bg-green-900/50', text: 'text-green-300' },
  cancelled: { bg: 'bg-red-900/50', text: 'text-red-300' },
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

  // Fetch campaigns
  useEffect(() => {
    async function fetchCampaigns() {
      try {
        setIsLoading(true);
        const response = await api.get<OutreachCampaignListItem[]>('/outreach/campaigns');
        setCampaigns(response.data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load campaigns');
      } finally {
        setIsLoading(false);
      }
    }

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
      <div className="h-full flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex-shrink-0 px-6 py-4 border-b border-gray-800">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                <Mail className="w-6 h-6 text-indigo-400" />
                Outreach Campaigns
              </h1>
              <p className="text-sm text-gray-400 mt-1">
                Email campaigns created from void analysis results
              </p>
            </div>

            <Link
              to="/chat"
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500
                         text-white rounded-lg transition-colors"
            >
              <Plus className="w-4 h-4" />
              New Campaign
            </Link>
          </div>

          {/* Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
            <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
              <div className="text-2xl font-bold text-white">{stats.total}</div>
              <div className="text-xs text-gray-400">Total Campaigns</div>
            </div>
            <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
              <div className="text-2xl font-bold text-green-400">{stats.totalEmails}</div>
              <div className="text-xs text-gray-400">Emails Sent</div>
            </div>
            <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
              <div className="text-2xl font-bold text-blue-400">{stats.totalOpens}</div>
              <div className="text-xs text-gray-400">Opens</div>
            </div>
            <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
              <div className="text-2xl font-bold text-purple-400">{avgOpenRate}%</div>
              <div className="text-xs text-gray-400">Avg Open Rate</div>
            </div>
            <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
              <div className="text-2xl font-bold text-amber-400">{stats.totalReplies}</div>
              <div className="text-xs text-gray-400">Replies</div>
            </div>
          </div>

          {/* Search & Filters */}
          <div className="flex items-center gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search campaigns..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg
                           text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as CampaignStatus | 'all')}
              className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-300
                         focus:outline-none focus:border-indigo-500"
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
              <div className="flex items-center gap-3 text-gray-400">
                <span className="w-5 h-5 border-2 border-gray-600 border-t-indigo-500 rounded-full animate-spin" />
                Loading campaigns...
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-center">
                <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
                <p className="text-red-400">{error}</p>
              </div>
            </div>
          ) : filteredCampaigns.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-center">
              <Mail className="w-16 h-16 text-gray-600 mb-4" />
              <h3 className="text-lg font-medium text-white mb-2">No campaigns yet</h3>
              <p className="text-gray-400 mb-4 max-w-md">
                Create your first outreach campaign from a void analysis. Ask SpaceFit to
                run a void analysis and then reach out to the identified tenants.
              </p>
              <Link
                to="/chat"
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500
                           text-white rounded-lg transition-colors"
              >
                <Plus className="w-4 h-4" />
                Start a Void Analysis
              </Link>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredCampaigns.map((campaign) => (
                <div
                  key={campaign.id}
                  className="bg-gray-800/50 border border-gray-700 rounded-lg p-4
                             hover:border-gray-600 transition-colors cursor-pointer"
                  onClick={() => {
                    // TODO: Open campaign detail modal
                  }}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-1">
                        <h3 className="text-lg font-medium text-white truncate">
                          {campaign.name}
                        </h3>
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-medium
                            ${STATUS_COLORS[campaign.status].bg}
                            ${STATUS_COLORS[campaign.status].text}`}
                        >
                          {campaign.status}
                        </span>
                      </div>
                      <p className="text-sm text-gray-400 truncate">
                        {campaign.property_name || 'No property name'}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        Created {formatDate(campaign.created_at)}
                        {campaign.sent_at && ` • Sent ${formatDate(campaign.sent_at)}`}
                      </p>
                    </div>

                    {/* Stats */}
                    <div className="flex items-center gap-6 ml-4">
                      <div className="text-center">
                        <div className="flex items-center gap-1 text-gray-400">
                          <Send className="w-4 h-4" />
                          <span className="text-lg font-semibold text-white">
                            {campaign.sent_count}
                          </span>
                        </div>
                        <div className="text-xs text-gray-500">Sent</div>
                      </div>

                      <div className="text-center">
                        <div className="flex items-center gap-1 text-gray-400">
                          <Eye className="w-4 h-4" />
                          <span className="text-lg font-semibold text-white">
                            {campaign.opened_count}
                          </span>
                        </div>
                        <div className="text-xs text-gray-500">
                          Opened ({calculateOpenRate(campaign)}%)
                        </div>
                      </div>

                      <div className="text-center">
                        <div className="flex items-center gap-1 text-gray-400">
                          <MessageCircle className="w-4 h-4" />
                          <span className="text-lg font-semibold text-white">
                            {campaign.replied_count}
                          </span>
                        </div>
                        <div className="text-xs text-gray-500">Replied</div>
                      </div>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          // TODO: Open actions menu
                        }}
                        className="p-2 text-gray-400 hover:text-white hover:bg-gray-700
                                   rounded-lg transition-colors"
                      >
                        <MoreVertical className="w-5 h-5" />
                      </button>
                    </div>
                  </div>

                  {/* Progress bar for sent campaigns */}
                  {campaign.status === 'sent' && campaign.sent_count > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-700">
                      <div className="flex items-center gap-2 text-xs text-gray-400 mb-1">
                        <span>Open rate</span>
                        <span className="text-white font-medium">
                          {calculateOpenRate(campaign)}%
                        </span>
                      </div>
                      <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-500 transition-all"
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
    </AppLayout>
  );
}
