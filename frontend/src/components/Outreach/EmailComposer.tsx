import { useState, useCallback } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Underline from '@tiptap/extension-underline';
import {
  Bold,
  Italic,
  Underline as UnderlineIcon,
  List,
  ListOrdered,
  Link as LinkIcon,
  Heading2,
  X,
  Sparkles,
  PenLine,
  Save,
  Send,
  Plus,
  Trash2,
} from 'lucide-react';
import api from '../../lib/axios';
import type { CreateCampaignRequest, CreateRecipientRequest } from '../../types/outreach';

interface EmailComposerProps {
  onClose: () => void;
  onCampaignCreated: () => void;
  /** Pre-populated recipients from tenant match flow */
  initialRecipients?: CreateRecipientRequest[];
  propertyName?: string;
  propertyAddress?: string;
}

type ComposeMode = 'choose' | 'manual' | 'ai';

interface RecipientRow {
  id: string;
  tenant_name: string;
  contact_email: string;
  contact_name: string;
}

function ToolbarButton({
  onClick,
  isActive,
  children,
  title,
}: {
  onClick: () => void;
  isActive?: boolean;
  children: React.ReactNode;
  title: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={`p-1.5 rounded-md transition-colors ${
        isActive
          ? 'bg-[var(--accent-subtle)] text-[var(--accent)]'
          : 'text-industrial-muted hover:text-industrial hover:bg-[var(--bg-tertiary)]'
      }`}
    >
      {children}
    </button>
  );
}

export function EmailComposer({
  onClose,
  onCampaignCreated,
  initialRecipients = [],
  propertyName = '',
  propertyAddress = '',
}: EmailComposerProps) {
  const [mode, setMode] = useState<ComposeMode>(initialRecipients.length > 0 ? 'manual' : 'choose');
  const [campaignName, setCampaignName] = useState(
    propertyName ? `Outreach: ${propertyName}` : ''
  );
  const [subject, setSubject] = useState('');
  const [fromName, setFromName] = useState('');
  const [fromEmail, setFromEmail] = useState('');
  const [replyTo, setReplyTo] = useState('');
  const [recipients, setRecipients] = useState<RecipientRow[]>(
    initialRecipients.map((r, i) => ({
      id: `r-${i}`,
      tenant_name: r.tenant_name,
      contact_email: r.contact_email,
      contact_name: r.contact_name || '',
    }))
  );
  const [isSaving, setIsSaving] = useState(false);
  const [isSavingTemplate, setIsSavingTemplate] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [2, 3] },
      }),
      Link.configure({ openOnClick: false }),
      Underline,
    ],
    content: '',
    editorProps: {
      attributes: {
        class:
          'prose prose-sm max-w-none min-h-[200px] px-4 py-3 focus:outline-none text-industrial text-sm leading-relaxed',
      },
    },
  });

  const addRecipient = useCallback(() => {
    setRecipients((prev) => [
      ...prev,
      { id: `r-${Date.now()}`, tenant_name: '', contact_email: '', contact_name: '' },
    ]);
  }, []);

  const removeRecipient = useCallback((id: string) => {
    setRecipients((prev) => prev.filter((r) => r.id !== id));
  }, []);

  const updateRecipient = useCallback((id: string, field: keyof RecipientRow, value: string) => {
    setRecipients((prev) =>
      prev.map((r) => (r.id === id ? { ...r, [field]: value } : r))
    );
  }, []);

  const handleSaveDraft = async () => {
    if (!campaignName || !subject || !fromName || !fromEmail) {
      setError('Please fill in campaign name, subject, sender name, and sender email.');
      return;
    }
    if (recipients.filter((r) => r.contact_email).length === 0) {
      setError('Please add at least one recipient with an email address.');
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      const payload: CreateCampaignRequest = {
        name: campaignName,
        property_address: propertyAddress || 'N/A',
        property_name: propertyName || undefined,
        subject,
        body_template: editor?.getHTML() || '',
        from_name: fromName,
        from_email: fromEmail,
        reply_to: replyTo || undefined,
        recipients: recipients
          .filter((r) => r.contact_email)
          .map((r) => ({
            tenant_name: r.tenant_name || r.contact_email,
            contact_email: r.contact_email,
            contact_name: r.contact_name || undefined,
          })),
      };

      await api.post('/outreach/campaigns', payload);
      onCampaignCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create campaign');
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveAsTemplate = async () => {
    if (!subject) {
      setError('Please fill in a subject line before saving as template.');
      return;
    }

    setIsSavingTemplate(true);
    setError(null);

    try {
      await api.post('/outreach/templates', {
        name: campaignName || 'Untitled template',
        subject_template: subject,
        body_template: editor?.getHTML() || '',
        category: 'manual',
      });
      setIsSavingTemplate(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save template');
      setIsSavingTemplate(false);
    }
  };

  const setLinkUrl = useCallback(() => {
    if (!editor) return;
    const url = window.prompt('Enter URL:');
    if (url) {
      editor.chain().focus().setLink({ href: url }).run();
    }
  }, [editor]);

  // Mode chooser
  if (mode === 'choose') {
    return (
      <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-2xl shadow-2xl max-w-2xl mx-auto overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-subtle)]">
          <h2 className="text-base font-semibold text-industrial">New campaign</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-[var(--bg-tertiary)] text-industrial-muted">
            <X size={18} />
          </button>
        </div>
        <div className="p-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
          <button
            onClick={() => setMode('ai')}
            className="flex flex-col items-start p-5 rounded-xl border border-[var(--border-default)] hover:border-[var(--accent)]/50 hover:bg-[var(--accent-subtle)] transition-all text-left group"
          >
            <Sparkles size={24} className="text-[var(--accent)] mb-3" />
            <span className="text-sm font-semibold text-industrial">AI draft</span>
            <span className="text-xs text-industrial-muted mt-1">
              Describe your outreach goal and let AI write the email
            </span>
          </button>
          <button
            onClick={() => setMode('manual')}
            className="flex flex-col items-start p-5 rounded-xl border border-[var(--border-default)] hover:border-[var(--accent)]/50 hover:bg-[var(--accent-subtle)] transition-all text-left group"
          >
            <PenLine size={24} className="text-industrial-secondary mb-3" />
            <span className="text-sm font-semibold text-industrial">Write manually</span>
            <span className="text-xs text-industrial-muted mt-1">
              Compose your own email with a rich text editor
            </span>
          </button>
        </div>
      </div>
    );
  }

  // AI mode — redirect to chat with outreach context
  if (mode === 'ai') {
    window.location.href = '/chat?context=outreach';
    return null;
  }

  // Manual compose mode
  return (
    <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-2xl shadow-2xl max-w-3xl mx-auto overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-subtle)]">
        <div className="flex items-center gap-3">
          <PenLine size={18} className="text-[var(--accent)]" />
          <h2 className="text-base font-semibold text-industrial">Compose campaign</h2>
        </div>
        <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-[var(--bg-tertiary)] text-industrial-muted">
          <X size={18} />
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="px-6 py-2 bg-[var(--bg-error)] border-b border-[var(--color-error)]/20">
          <p className="text-xs text-[var(--color-error)]">{error}</p>
        </div>
      )}

      <div className="px-6 py-5 space-y-4 max-h-[70vh] overflow-y-auto">
        {/* Campaign name */}
        <div>
          <label className="block text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-1">
            Campaign name
          </label>
          <input
            type="text"
            value={campaignName}
            onChange={(e) => setCampaignName(e.target.value)}
            placeholder="e.g. Q2 Outreach — Downtown Plaza"
            className="w-full px-3 py-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-subtle)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)]"
          />
        </div>

        {/* Sender info — two columns */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-1">
              From name
            </label>
            <input
              type="text"
              value={fromName}
              onChange={(e) => setFromName(e.target.value)}
              placeholder="Your name"
              className="w-full px-3 py-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-subtle)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)]"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-1">
              From email
            </label>
            <input
              type="email"
              value={fromEmail}
              onChange={(e) => setFromEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full px-3 py-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-subtle)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)]"
            />
          </div>
        </div>

        {/* Reply-to (optional) */}
        <div>
          <label className="block text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-1">
            Reply-to <span className="font-normal">(optional)</span>
          </label>
          <input
            type="email"
            value={replyTo}
            onChange={(e) => setReplyTo(e.target.value)}
            placeholder="replies@example.com"
            className="w-full px-3 py-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-subtle)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)]"
          />
        </div>

        {/* Subject */}
        <div>
          <label className="block text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-1">
            Subject line
          </label>
          <input
            type="text"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Leasing opportunity at {{property_name}}"
            className="w-full px-3 py-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-subtle)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)]"
          />
          <p className="text-[11px] text-industrial-muted mt-1">
            Use {'{{tenant_name}}'}, {'{{property_name}}'}, {'{{user_name}}'} for personalization
          </p>
        </div>

        {/* Rich text editor */}
        <div>
          <label className="block text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-1">
            Email body
          </label>
          <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] overflow-hidden">
            {/* Toolbar */}
            {editor && (
              <div className="flex items-center gap-0.5 px-2 py-1.5 border-b border-[var(--border-subtle)] bg-[var(--bg-tertiary)]">
                <ToolbarButton
                  onClick={() => editor.chain().focus().toggleBold().run()}
                  isActive={editor.isActive('bold')}
                  title="Bold"
                >
                  <Bold size={15} />
                </ToolbarButton>
                <ToolbarButton
                  onClick={() => editor.chain().focus().toggleItalic().run()}
                  isActive={editor.isActive('italic')}
                  title="Italic"
                >
                  <Italic size={15} />
                </ToolbarButton>
                <ToolbarButton
                  onClick={() => editor.chain().focus().toggleUnderline().run()}
                  isActive={editor.isActive('underline')}
                  title="Underline"
                >
                  <UnderlineIcon size={15} />
                </ToolbarButton>
                <div className="w-px h-4 bg-[var(--border-subtle)] mx-1" />
                <ToolbarButton
                  onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
                  isActive={editor.isActive('heading', { level: 2 })}
                  title="Heading"
                >
                  <Heading2 size={15} />
                </ToolbarButton>
                <ToolbarButton
                  onClick={() => editor.chain().focus().toggleBulletList().run()}
                  isActive={editor.isActive('bulletList')}
                  title="Bullet list"
                >
                  <List size={15} />
                </ToolbarButton>
                <ToolbarButton
                  onClick={() => editor.chain().focus().toggleOrderedList().run()}
                  isActive={editor.isActive('orderedList')}
                  title="Numbered list"
                >
                  <ListOrdered size={15} />
                </ToolbarButton>
                <div className="w-px h-4 bg-[var(--border-subtle)] mx-1" />
                <ToolbarButton
                  onClick={setLinkUrl}
                  isActive={editor.isActive('link')}
                  title="Insert link"
                >
                  <LinkIcon size={15} />
                </ToolbarButton>
              </div>
            )}

            {/* Editor content */}
            <EditorContent editor={editor} />
          </div>
        </div>

        {/* Recipients */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="block text-xs font-semibold text-industrial-muted uppercase tracking-wide">
              Recipients
            </label>
            <button
              type="button"
              onClick={addRecipient}
              className="inline-flex items-center gap-1 text-xs font-medium text-[var(--accent)] hover:text-[var(--accent-hover)] transition-colors"
            >
              <Plus size={12} />
              Add recipient
            </button>
          </div>
          <div className="space-y-2">
            {recipients.map((r) => (
              <div key={r.id} className="flex items-center gap-2">
                <input
                  type="text"
                  value={r.tenant_name}
                  onChange={(e) => updateRecipient(r.id, 'tenant_name', e.target.value)}
                  placeholder="Tenant name"
                  className="flex-1 px-3 py-1.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-subtle)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)]"
                />
                <input
                  type="email"
                  value={r.contact_email}
                  onChange={(e) => updateRecipient(r.id, 'contact_email', e.target.value)}
                  placeholder="email@example.com"
                  className="flex-1 px-3 py-1.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-subtle)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)]"
                />
                <button
                  type="button"
                  onClick={() => removeRecipient(r.id)}
                  className="p-1.5 rounded-md text-industrial-muted hover:text-[var(--color-error)] hover:bg-[var(--bg-error)] transition-colors"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
            {recipients.length === 0 && (
              <button
                type="button"
                onClick={addRecipient}
                className="w-full py-3 rounded-lg border border-dashed border-[var(--border-default)] text-xs text-industrial-muted hover:border-[var(--accent)]/50 hover:text-[var(--accent)] transition-colors"
              >
                Add your first recipient
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-[var(--border-subtle)] flex items-center justify-between">
        <button
          type="button"
          onClick={handleSaveAsTemplate}
          disabled={isSavingTemplate}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-industrial-secondary hover:bg-[var(--bg-tertiary)] transition-colors disabled:opacity-50"
        >
          <Save size={14} />
          {isSavingTemplate ? 'Saving...' : 'Save as template'}
        </button>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm font-medium text-industrial-secondary hover:bg-[var(--bg-tertiary)] transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSaveDraft}
            disabled={isSaving}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[var(--accent)] text-white text-sm font-semibold hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-50 shadow-lg shadow-[var(--accent)]/20"
          >
            <Send size={14} />
            {isSaving ? 'Creating...' : 'Save draft'}
          </button>
        </div>
      </div>
    </div>
  );
}
