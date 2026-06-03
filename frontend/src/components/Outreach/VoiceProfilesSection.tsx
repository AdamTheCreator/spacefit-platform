import { useState } from 'react';
import { Sparkles, Plus, Trash2, Pencil, Star, Check, X } from 'lucide-react';
import {
  useOutreachVoices,
  useCreateVoice,
  useUpdateVoice,
  useDeleteVoice,
  useSetDefaultVoice,
  type VoiceProfile,
} from '../../hooks/useOutreachVoices';

const INPUT_CLASS =
  'w-full px-3 py-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-subtle)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)]';
const LABEL_CLASS =
  'block text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-1';

interface VoiceFormState {
  name: string;
  tone: string;
  instructions: string;
  sample: string;
  signature: string;
  is_default: boolean;
}

function emptyForm(): VoiceFormState {
  return {
    name: '',
    tone: '',
    instructions: '',
    sample: '',
    signature: '',
    is_default: false,
  };
}

function toForm(v: VoiceProfile): VoiceFormState {
  return {
    name: v.name,
    tone: v.tone ?? '',
    instructions: v.instructions,
    sample: v.sample ?? '',
    signature: v.signature ?? '',
    is_default: v.is_default,
  };
}

/** Inline create/edit form for a single voice. */
function VoiceEditor({
  initial,
  busy,
  error,
  onSave,
  onCancel,
}: {
  initial: VoiceFormState;
  busy: boolean;
  error: string | null;
  onSave: (form: VoiceFormState) => void;
  onCancel: () => void;
}) {
  const [f, setF] = useState<VoiceFormState>(initial);
  const canSave = f.name.trim().length > 0 && f.instructions.trim().length > 0;

  const set = <K extends keyof VoiceFormState>(key: K, value: VoiceFormState[K]) =>
    setF((prev) => ({ ...prev, [key]: value }));

  return (
    <div className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-tertiary)] p-4 space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className={LABEL_CLASS}>Name</label>
          <input
            type="text"
            value={f.name}
            onChange={(e) => set('name', e.target.value)}
            placeholder="e.g. Warm intro"
            className={INPUT_CLASS}
          />
        </div>
        <div>
          <label className={LABEL_CLASS}>
            Tone <span className="font-normal lowercase">(optional)</span>
          </label>
          <input
            type="text"
            value={f.tone}
            onChange={(e) => set('tone', e.target.value)}
            placeholder="e.g. direct, friendly, low-key"
            className={INPUT_CLASS}
          />
        </div>
      </div>

      <div>
        <label className={LABEL_CLASS}>Voice instructions</label>
        <textarea
          value={f.instructions}
          onChange={(e) => set('instructions', e.target.value)}
          rows={4}
          placeholder="Write like me: short sentences, no corporate jargon, lead with the property's strongest angle, always end with a soft ask for a quick call…"
          className={`${INPUT_CLASS} resize-y`}
        />
        <p className="text-[11px] text-industrial-muted mt-1">
          Describe how you write — tone, phrasing, length, dos and don'ts. This is the
          prompt the AI follows.
        </p>
      </div>

      <div>
        <label className={LABEL_CLASS}>
          Sample email <span className="font-normal lowercase">(optional)</span>
        </label>
        <textarea
          value={f.sample}
          onChange={(e) => set('sample', e.target.value)}
          rows={3}
          placeholder="Paste a real email you wrote. The AI matches its rhythm and vocabulary (it won't copy the specifics)."
          className={`${INPUT_CLASS} resize-y`}
        />
      </div>

      <div>
        <label className={LABEL_CLASS}>
          Signature <span className="font-normal lowercase">(optional)</span>
        </label>
        <textarea
          value={f.signature}
          onChange={(e) => set('signature', e.target.value)}
          rows={2}
          placeholder={'Best,\nJane Doe · Principal · (555) 010-0100'}
          className={`${INPUT_CLASS} resize-y`}
        />
      </div>

      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={f.is_default}
          onChange={(e) => set('is_default', e.target.checked)}
          className="rounded border-[var(--border-default)]"
        />
        <span className="text-sm text-industrial-secondary">
          Use this as my default voice
        </span>
      </label>

      {error && <p className="text-xs text-[var(--color-error)]">{error}</p>}

      <div className="flex items-center justify-end gap-2 pt-1">
        <button type="button" onClick={onCancel} className="btn-industrial btn-sm">
          <X size={14} />
          Cancel
        </button>
        <button
          type="button"
          onClick={() => onSave(f)}
          disabled={!canSave || busy}
          className="btn-industrial-primary btn-sm disabled:opacity-50"
        >
          <Check size={14} />
          {busy ? 'Saving…' : 'Save voice'}
        </button>
      </div>
    </div>
  );
}

/** Read-only row for a saved voice with edit / default / delete actions. */
function VoiceRow({
  voice,
  onEdit,
  onMakeDefault,
  onDelete,
  busy,
}: {
  voice: VoiceProfile;
  onEdit: () => void;
  onMakeDefault: () => void;
  onDelete: () => void;
  busy: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-secondary)] px-4 py-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-industrial truncate">
            {voice.name}
          </span>
          {voice.is_default && (
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold tracking-wider uppercase text-[var(--accent)] px-1.5 py-0.5 rounded bg-[var(--accent)]/10">
              <Star size={10} />
              Default
            </span>
          )}
        </div>
        {voice.tone && (
          <p className="text-xs text-industrial-muted mt-0.5 truncate">{voice.tone}</p>
        )}
        <p className="text-xs text-industrial-secondary mt-1 line-clamp-2">
          {voice.instructions}
        </p>
      </div>
      <div className="flex items-center gap-1 shrink-0">
        {!voice.is_default && (
          <button
            type="button"
            onClick={onMakeDefault}
            disabled={busy}
            title="Make default"
            className="p-1.5 rounded-md text-industrial-muted hover:text-[var(--accent)] hover:bg-[var(--bg-tertiary)] transition-colors disabled:opacity-50"
          >
            <Star size={14} />
          </button>
        )}
        <button
          type="button"
          onClick={onEdit}
          title="Edit"
          className="p-1.5 rounded-md text-industrial-muted hover:text-industrial hover:bg-[var(--bg-tertiary)] transition-colors"
        >
          <Pencil size={14} />
        </button>
        <button
          type="button"
          onClick={onDelete}
          disabled={busy}
          title="Delete"
          className="p-1.5 rounded-md text-industrial-muted hover:text-[var(--color-error)] hover:bg-[var(--bg-error)] transition-colors disabled:opacity-50"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}

export function VoiceProfilesSection() {
  const { data: voices, isLoading, isError, refetch } = useOutreachVoices();
  const createVoice = useCreateVoice();
  const updateVoice = useUpdateVoice();
  const deleteVoice = useDeleteVoice();
  const setDefaultVoice = useSetDefaultVoice();

  const [expanded, setExpanded] = useState(false);
  // null = not editing; 'new' = create form; otherwise a voice id being edited.
  const [editing, setEditing] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const list = voices ?? [];
  const defaultVoice = list.find((v) => v.is_default);
  const busy =
    createVoice.isPending ||
    updateVoice.isPending ||
    deleteVoice.isPending ||
    setDefaultVoice.isPending;

  const summary = isLoading
    ? 'Loading…'
    : isError
      ? 'Could not load voices'
      : list.length === 0
        ? 'Teach the AI to write outreach in your voice.'
        : `${list.length} voice${list.length === 1 ? '' : 's'}${
            defaultVoice ? ` · default: ${defaultVoice.name}` : ''
          }`;

  const handleSave = async (form: VoiceFormState) => {
    setFormError(null);
    const payload = {
      name: form.name.trim(),
      instructions: form.instructions.trim(),
      tone: form.tone.trim() || null,
      sample: form.sample.trim() || null,
      signature: form.signature.trim() || null,
      is_default: form.is_default,
    };
    try {
      if (editing && editing !== 'new') {
        await updateVoice.mutateAsync({ id: editing, data: payload });
      } else {
        await createVoice.mutateAsync(payload);
      }
      setEditing(null);
    } catch {
      setFormError('Could not save the voice. Please try again.');
    }
  };

  return (
    <div className="card-industrial">
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
        className="w-full flex items-center gap-3 text-left"
      >
        <div className="w-8 h-8 rounded-lg bg-[var(--accent)]/10 flex items-center justify-center shrink-0">
          <Sparkles size={16} className="text-[var(--accent)]" />
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="text-sm font-semibold text-industrial">Email voice</h2>
          <p className="text-xs text-industrial-muted mt-0.5 truncate">{summary}</p>
        </div>
        <span
          className={`text-industrial-muted transition-transform ${expanded ? 'rotate-180' : ''}`}
          aria-hidden="true"
        >
          ▾
        </span>
      </button>

      {expanded && (
        <div className="mt-5 pt-5 border-t border-[var(--border-subtle)] space-y-4">
          <p className="text-xs text-industrial-secondary leading-relaxed">
            Save one or more voice profiles, then pick one when drafting an outreach
            campaign with AI. The generator uses your instructions (and an optional
            sample) so emails read like you wrote them. Drafting runs through your
            configured AI provider — set up a Hugging Face or other key under{' '}
            <strong className="text-industrial">AI Model</strong> above to keep it on
            your own key.
          </p>

          {isError && (
            <div className="rounded-xl border border-[var(--color-error)]/30 bg-[var(--bg-error)] px-4 py-3 text-xs text-[var(--color-error)] flex items-center justify-between gap-3">
              <span>Couldn't load your voices. The backend may be waking up.</span>
              <button onClick={() => refetch()} className="btn-industrial btn-sm">
                Retry
              </button>
            </div>
          )}

          {!isError && (
            <div className="space-y-2">
              {list.map((voice) =>
                editing === voice.id ? (
                  <VoiceEditor
                    key={voice.id}
                    initial={toForm(voice)}
                    busy={busy}
                    error={formError}
                    onSave={handleSave}
                    onCancel={() => {
                      setEditing(null);
                      setFormError(null);
                    }}
                  />
                ) : (
                  <VoiceRow
                    key={voice.id}
                    voice={voice}
                    busy={busy}
                    onEdit={() => {
                      setEditing(voice.id);
                      setFormError(null);
                    }}
                    onMakeDefault={() => setDefaultVoice.mutate(voice.id)}
                    onDelete={() => {
                      if (
                        window.confirm(`Delete the "${voice.name}" voice?`)
                      ) {
                        deleteVoice.mutate(voice.id);
                      }
                    }}
                  />
                ),
              )}

              {list.length === 0 && editing !== 'new' && !isLoading && (
                <div className="text-center py-8 bg-[var(--bg-tertiary)] rounded-xl border border-[var(--border-subtle)]">
                  <Sparkles size={28} className="text-industrial-muted mx-auto mb-2" />
                  <p className="text-sm text-industrial-muted">No voices yet</p>
                  <p className="text-xs text-industrial-muted mt-1">
                    Create one to draft outreach in your own style.
                  </p>
                </div>
              )}

              {editing === 'new' ? (
                <VoiceEditor
                  initial={emptyForm()}
                  busy={busy}
                  error={formError}
                  onSave={handleSave}
                  onCancel={() => {
                    setEditing(null);
                    setFormError(null);
                  }}
                />
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    setEditing('new');
                    setFormError(null);
                  }}
                  className="w-full inline-flex items-center justify-center gap-2 py-2.5 rounded-lg border border-dashed border-[var(--border-default)] text-xs font-medium text-industrial-secondary hover:border-[var(--accent)]/50 hover:text-[var(--accent)] transition-colors"
                >
                  <Plus size={14} />
                  Add voice
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
