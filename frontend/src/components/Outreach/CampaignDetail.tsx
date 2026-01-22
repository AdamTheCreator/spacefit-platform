import { useState } from 'react';
import {
  X,
  Send,
  Eye,
  MousePointerClick,
  MessageCircle,
  AlertCircle,
  Clock,
  Users,
  Mail,
  ExternalLink,
} from 'lucide-react';
import type { OutreachCampaign, OutreachRecipient, CampaignStatus } from '../../types/outreach';

interface CampaignDetailProps {
  campaign: OutreachCampaign;
  onClose: () => void;
  onSend?: () => void;
}

const STATUS_COLORS: Record<CampaignStatus, { bg: string; text: string; border: string }> = {
  draft: { bg: 'bg-gray-700', text: 'text-gray-300', border: 'border-gray-600' },
  scheduled: { bg: 'bg-blue-900/50', text: 'text-blue-300', border: 'border-blue-700' },
  sending: { bg: 'bg-yellow-900/50', text: 'text-yellow-300', border: 'border-yellow-700' },
  sent: { bg: 'bg-green-900/50', text: 'text-green-300', border: 'border-green-700' },
  cancelled: { bg: 'bg-red-900/50', text: 'text-red-300', border: 'border-red-700' },
};

function formatDateTime(dateStr: string | null): string {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export function CampaignDetail({ campaign, onClose, onSend }: CampaignDetailProps) {
  const [activeTab, setActiveTab] = useState<'overview' | 'recipients' | 'preview'>('overview');

  const openRate = campaign.sent_count > 0
    ? Math.round((campaign.opened_count / campaign.sent_count) * 100)
    : 0;

  const clickRate = campaign.sent_count > 0
    ? Math.round((campaign.clicked_count / campaign.sent_count) * 100)
    : 0;

  const replyRate = campaign.sent_count > 0
    ? Math.round((campaign.replied_count / campaign.sent_count) * 100)
    : 0;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl border border-gray-700 w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-gray-700">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h2 className="text-xl font-bold text-white">{campaign.name}</h2>
              <span
                className={`px-2 py-1 rounded text-xs font-medium
                  ${STATUS_COLORS[campaign.status].bg}
                  ${STATUS_COLORS[campaign.status].text}
                  ${STATUS_COLORS[campaign.status].border} border`}
              >
                {campaign.status}
              </span>
            </div>
            <p className="text-gray-400 text-sm">
              {campaign.property_name || campaign.property_address}
            </p>
          </div>

          <div className="flex items-center gap-2">
            {campaign.status === 'draft' && onSend && (
              <button
                onClick={onSend}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500
                           text-white rounded-lg transition-colors"
              >
                <Send className="w-4 h-4" />
                Send Campaign
              </button>
            )}
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-white hover:bg-gray-700
                         rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-700">
          {(['overview', 'recipients', 'preview'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-6 py-3 text-sm font-medium transition-colors
                ${activeTab === tab
                  ? 'text-white border-b-2 border-indigo-500'
                  : 'text-gray-400 hover:text-white'
                }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Stats Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-gray-900/50 rounded-lg p-4 border border-gray-700">
                  <div className="flex items-center gap-2 text-gray-400 mb-1">
                    <Users className="w-4 h-4" />
                    <span className="text-xs">Recipients</span>
                  </div>
                  <div className="text-2xl font-bold text-white">
                    {campaign.total_recipients}
                  </div>
                </div>

                <div className="bg-gray-900/50 rounded-lg p-4 border border-gray-700">
                  <div className="flex items-center gap-2 text-gray-400 mb-1">
                    <Eye className="w-4 h-4" />
                    <span className="text-xs">Opened</span>
                  </div>
                  <div className="text-2xl font-bold text-blue-400">
                    {campaign.opened_count}
                    <span className="text-sm text-gray-400 ml-1">({openRate}%)</span>
                  </div>
                </div>

                <div className="bg-gray-900/50 rounded-lg p-4 border border-gray-700">
                  <div className="flex items-center gap-2 text-gray-400 mb-1">
                    <MousePointerClick className="w-4 h-4" />
                    <span className="text-xs">Clicked</span>
                  </div>
                  <div className="text-2xl font-bold text-purple-400">
                    {campaign.clicked_count}
                    <span className="text-sm text-gray-400 ml-1">({clickRate}%)</span>
                  </div>
                </div>

                <div className="bg-gray-900/50 rounded-lg p-4 border border-gray-700">
                  <div className="flex items-center gap-2 text-gray-400 mb-1">
                    <MessageCircle className="w-4 h-4" />
                    <span className="text-xs">Replied</span>
                  </div>
                  <div className="text-2xl font-bold text-green-400">
                    {campaign.replied_count}
                    <span className="text-sm text-gray-400 ml-1">({replyRate}%)</span>
                  </div>
                </div>
              </div>

              {/* Campaign Details */}
              <div className="bg-gray-900/50 rounded-lg border border-gray-700 p-4">
                <h3 className="text-sm font-medium text-gray-400 mb-3">Campaign Details</h3>
                <dl className="space-y-3">
                  <div className="flex justify-between">
                    <dt className="text-gray-400">Property</dt>
                    <dd className="text-white">{campaign.property_name || campaign.property_address}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-400">Subject</dt>
                    <dd className="text-white truncate max-w-md">{campaign.subject}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-400">From</dt>
                    <dd className="text-white">{campaign.from_name} &lt;{campaign.from_email}&gt;</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-400">Created</dt>
                    <dd className="text-white">{formatDateTime(campaign.created_at)}</dd>
                  </div>
                  {campaign.sent_at && (
                    <div className="flex justify-between">
                      <dt className="text-gray-400">Sent</dt>
                      <dd className="text-white">{formatDateTime(campaign.sent_at)}</dd>
                    </div>
                  )}
                </dl>
              </div>

              {/* Bounces Warning */}
              {campaign.bounced_count > 0 && (
                <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-4 flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-red-400 font-medium">
                      {campaign.bounced_count} email{campaign.bounced_count !== 1 ? 's' : ''} bounced
                    </h4>
                    <p className="text-red-400/80 text-sm mt-1">
                      Some emails could not be delivered. Check the recipients tab for details.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'recipients' && (
            <div className="space-y-4">
              {campaign.recipients && campaign.recipients.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-gray-700">
                        <th className="text-left py-3 px-4 text-xs font-medium text-gray-400 uppercase">
                          Tenant
                        </th>
                        <th className="text-left py-3 px-4 text-xs font-medium text-gray-400 uppercase">
                          Category
                        </th>
                        <th className="text-left py-3 px-4 text-xs font-medium text-gray-400 uppercase">
                          Status
                        </th>
                        <th className="text-left py-3 px-4 text-xs font-medium text-gray-400 uppercase">
                          Activity
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-700">
                      {campaign.recipients.map((recipient) => (
                        <RecipientRow key={recipient.id} recipient={recipient} />
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-12 text-gray-400">
                  No recipients data available
                </div>
              )}
            </div>
          )}

          {activeTab === 'preview' && (
            <div className="space-y-4">
              <div className="bg-gray-900/50 rounded-lg border border-gray-700 p-4">
                <h3 className="text-sm font-medium text-gray-400 mb-2">Subject</h3>
                <p className="text-white">{campaign.subject}</p>
              </div>
              <div className="bg-gray-900/50 rounded-lg border border-gray-700 p-4">
                <h3 className="text-sm font-medium text-gray-400 mb-2">Body</h3>
                <div
                  className="prose prose-invert prose-sm max-w-none"
                  dangerouslySetInnerHTML={{ __html: campaign.body_template }}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function RecipientRow({ recipient }: { recipient: OutreachRecipient }) {
  const statusColors: Record<string, string> = {
    pending: 'text-gray-400',
    sent: 'text-blue-400',
    delivered: 'text-blue-400',
    opened: 'text-green-400',
    clicked: 'text-purple-400',
    replied: 'text-amber-400',
    bounced: 'text-red-400',
    unsubscribed: 'text-gray-500',
  };

  return (
    <tr className="hover:bg-gray-700/30">
      <td className="py-3 px-4">
        <div>
          <div className="text-white font-medium">{recipient.tenant_name}</div>
          <div className="text-gray-400 text-sm">{recipient.contact_email}</div>
        </div>
      </td>
      <td className="py-3 px-4">
        <span className="text-gray-300">{recipient.category || '-'}</span>
        {recipient.match_score && (
          <span className="ml-2 text-xs text-gray-500">
            {recipient.match_score.toFixed(0)}% match
          </span>
        )}
      </td>
      <td className="py-3 px-4">
        <span className={`capitalize ${statusColors[recipient.status] || 'text-gray-400'}`}>
          {recipient.status}
        </span>
      </td>
      <td className="py-3 px-4 text-sm text-gray-400">
        {recipient.replied_at ? (
          <span className="text-amber-400">Replied {formatDateTime(recipient.replied_at)}</span>
        ) : recipient.clicked_at ? (
          <span className="text-purple-400">Clicked {formatDateTime(recipient.clicked_at)}</span>
        ) : recipient.opened_at ? (
          <span className="text-green-400">Opened {formatDateTime(recipient.opened_at)}</span>
        ) : recipient.sent_at ? (
          <span>Sent {formatDateTime(recipient.sent_at)}</span>
        ) : (
          <span>-</span>
        )}
      </td>
    </tr>
  );
}
