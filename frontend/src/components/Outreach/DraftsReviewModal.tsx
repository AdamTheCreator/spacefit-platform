import { useState } from 'react';
import { Check, Edit3, Send, X, Loader2 } from 'lucide-react';
import api from '../../lib/axios';

export interface OutreachDraft {
  tenant_name: string;
  recipient_email: string;
  subject: string;
  body: string;
  rationale: string;
}

interface DraftsReviewModalProps {
  drafts: OutreachDraft[];
  propertyAddress: string;
  onClose: () => void;
  onSent?: () => void;
}

export function DraftsReviewModal({
  drafts: initialDrafts,
  propertyAddress,
  onClose,
  onSent,
}: DraftsReviewModalProps) {
  const [drafts, setDrafts] = useState(initialDrafts);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateDraft = (index: number, field: keyof OutreachDraft, value: string) => {
    setDrafts((prev) =>
      prev.map((d, i) => (i === index ? { ...d, [field]: value } : d))
    );
  };

  const removeDraft = (index: number) => {
    setDrafts((prev) => prev.filter((_, i) => i !== index));
  };

  const handleApproveAndSend = async () => {
    if (drafts.length === 0) return;
    setSending(true);
    setError(null);

    try {
      // Create a campaign from the drafts
      const res = await api.post('/outreach/campaigns', {
        name: `Outreach: ${propertyAddress}`,
        property_address: propertyAddress,
        subject: drafts[0].subject,
        body_template: drafts[0].body,
        from_name: 'Perigee AI',
        from_email: 'outreach@perigee.test',
        recipients: drafts.map((d) => ({
          tenant_name: d.tenant_name,
          contact_email: d.recipient_email || `${d.tenant_name.toLowerCase().replace(/\s+/g, '.')}@example.com`,
          category: d.rationale,
        })),
      });

      const campaignId = res.data.id;

      // Send the campaign
      await api.post(`/outreach/campaigns/${campaignId}/send`);
      setSent(true);
      onSent?.();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to send campaign';
      setError(msg);
    } finally {
      setSending(false);
    }
  };

  if (sent) {
    return (
      <div className="border border-[var(--color-success)]/30 bg-[var(--bg-success)] p-4 rounded-lg">
        <div className="flex items-center gap-2 text-[var(--color-success)] font-mono text-sm">
          <Check size={16} />
          {drafts.length} outreach emails sent successfully!
        </div>
        <button onClick={onClose} className="font-mono text-xs text-industrial-muted mt-2 underline">
          Dismiss
        </button>
      </div>
    );
  }

  return (
    <div className="border border-industrial-subtle bg-[var(--bg-secondary)] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 bg-[var(--bg-tertiary)] border-b border-industrial-subtle flex items-center justify-between">
        <h3 className="font-mono text-sm font-semibold text-industrial">
          {drafts.length} Outreach Drafts
        </h3>
        <button onClick={onClose} className="text-industrial-muted hover:text-industrial">
          <X size={16} />
        </button>
      </div>

      {/* Drafts list */}
      <div className="divide-y divide-[var(--border-subtle)] max-h-96 overflow-y-auto">
        {drafts.map((draft, i) => (
          <div key={i} className="p-4">
            <div className="flex items-start justify-between gap-3 mb-2">
              <div className="flex-1">
                <p className="font-mono text-sm font-medium text-industrial">
                  {draft.tenant_name}
                </p>
                <p className="font-mono text-[10px] text-industrial-muted">
                  {draft.recipient_email || '(no email)'}
                </p>
              </div>
              <div className="flex gap-1">
                <button
                  onClick={() => setEditingIndex(editingIndex === i ? null : i)}
                  className="p-1 text-industrial-muted hover:text-[var(--accent)]"
                  title="Edit"
                >
                  <Edit3 size={14} />
                </button>
                <button
                  onClick={() => removeDraft(i)}
                  className="p-1 text-industrial-muted hover:text-[var(--color-error)]"
                  title="Remove"
                >
                  <X size={14} />
                </button>
              </div>
            </div>

            {editingIndex === i ? (
              <div className="space-y-2">
                <input
                  value={draft.subject}
                  onChange={(e) => updateDraft(i, 'subject', e.target.value)}
                  className="w-full bg-[var(--bg-primary)] border border-industrial-subtle px-2 py-1 font-mono text-xs text-industrial"
                  placeholder="Subject"
                />
                <textarea
                  value={draft.body}
                  onChange={(e) => updateDraft(i, 'body', e.target.value)}
                  rows={6}
                  className="w-full bg-[var(--bg-primary)] border border-industrial-subtle px-2 py-1 font-mono text-xs text-industrial resize-y"
                />
                <button
                  onClick={() => setEditingIndex(null)}
                  className="font-mono text-[10px] text-[var(--accent)] underline"
                >
                  Done editing
                </button>
              </div>
            ) : (
              <>
                <p className="font-mono text-xs text-industrial-secondary mb-1">
                  <strong>Subject:</strong> {draft.subject}
                </p>
                {draft.rationale && (
                  <p className="font-mono text-[10px] text-[var(--accent)] mb-1">
                    {draft.rationale}
                  </p>
                )}
                <p className="font-mono text-[10px] text-industrial-muted line-clamp-3">
                  {draft.body}
                </p>
              </>
            )}
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 bg-[var(--bg-tertiary)] border-t border-industrial-subtle flex items-center justify-between">
        {error && (
          <p className="font-mono text-xs text-[var(--color-error)] flex-1 mr-3">{error}</p>
        )}
        <div className="flex items-center gap-3 ml-auto">
          <button onClick={onClose} className="btn-industrial text-xs">
            Cancel
          </button>
          <button
            onClick={handleApproveAndSend}
            disabled={sending || drafts.length === 0}
            className="btn-industrial-primary text-xs disabled:opacity-50"
          >
            {sending ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Sending...
              </>
            ) : (
              <>
                <Send size={14} />
                Approve & Send ({drafts.length})
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
