import { useState } from 'react';
import { X, Search, Check, Layers } from 'lucide-react';
import { useProjects } from '../../hooks/useProjects';
import { usePromoteChat } from '../../hooks/usePromoteChat';

interface PromoteModalProps {
  sessionId: string;
  onClose: () => void;
  onPromoted: (project: { id: string; name: string }) => void;
}

type Mode = 'existing' | 'new';

export function PromoteModal({ sessionId, onClose, onPromoted }: PromoteModalProps) {
  const [mode, setMode] = useState<Mode>('existing');
  const [query, setQuery] = useState('');
  const [pickedId, setPickedId] = useState<string | null>(null);
  const [newName, setNewName] = useState('');
  const [newAddress, setNewAddress] = useState('');

  const { data: projectList, isLoading } = useProjects({ search: query || undefined });
  const projects = projectList?.items ?? [];
  const promote = usePromoteChat();

  const canSubmit =
    mode === 'existing' ? !!pickedId : newName.trim().length > 0;

  const handleSubmit = async () => {
    if (!canSubmit || promote.isPending) return;
    try {
      const result =
        mode === 'existing'
          ? await promote.mutateAsync({ sessionId, projectId: pickedId! })
          : await promote.mutateAsync({
              sessionId,
              newProject: {
                name: newName.trim(),
                propertyAddress: newAddress.trim() || undefined,
              },
            });
      onPromoted({
        id: result.project_id!,
        name: result.project_name ?? newName.trim(),
      });
      onClose();
    } catch {
      // Surfaced via promote.isError below.
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative w-full max-w-lg mx-4 bg-[var(--bg-elevated)] rounded-2xl border border-[var(--border-default)] shadow-xl overflow-hidden animate-scale-in">
        {/* Header */}
        <div className="flex items-start gap-3 px-6 py-5 border-b border-[var(--border-subtle)]">
          <div className="flex-shrink-0 w-11 h-11 rounded-xl bg-[var(--accent-subtle)] text-[var(--accent)] flex items-center justify-center">
            <Layers size={20} />
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-base font-semibold text-industrial">
              Save chat to a project
            </h2>
            <p className="text-[13px] text-industrial-secondary mt-0.5">
              Future messages will ground in your project&apos;s uploaded data.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-industrial-muted hover:bg-[var(--bg-tertiary)] transition-colors"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-[var(--border-subtle)]">
          {(
            [
              ['existing', 'Pick existing'],
              ['new', 'Create new'],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              onClick={() => setMode(id)}
              className={`flex-1 px-4 py-3 text-sm font-medium transition-colors border-b-2 ${
                mode === id
                  ? 'border-[var(--accent)] text-industrial bg-[var(--bg-primary)]'
                  : 'border-transparent text-industrial-muted bg-[var(--bg-secondary)] hover:text-industrial-secondary'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Body */}
        {mode === 'existing' ? (
          <div className="p-5">
            <div className="flex items-center gap-2 px-3 py-2.5 mb-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] focus-within:border-[var(--accent)]/50 transition-colors">
              <Search size={15} className="text-industrial-muted flex-shrink-0" />
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search your projects"
                className="flex-1 bg-transparent text-sm text-industrial placeholder:text-industrial-muted outline-none"
              />
            </div>
            <div className="max-h-64 overflow-y-auto grid gap-1.5 scrollbar-thin">
              {isLoading ? (
                <p className="text-sm text-industrial-muted px-1 py-6 text-center">
                  Loading projects…
                </p>
              ) : projects.length === 0 ? (
                <p className="text-sm text-industrial-muted px-1 py-6 text-center">
                  {query
                    ? 'No projects match your search.'
                    : 'No projects yet — create one instead.'}
                </p>
              ) : (
                projects.map((p) => {
                  const picked = pickedId === p.id;
                  return (
                    <button
                      key={p.id}
                      onClick={() => setPickedId(p.id)}
                      className={`flex items-center justify-between gap-3 px-3.5 py-3 rounded-lg border text-left transition-colors ${
                        picked
                          ? 'border-[var(--accent)] bg-[var(--accent-subtle)]'
                          : 'border-[var(--border-subtle)] bg-[var(--bg-primary)] hover:border-[var(--border-strong)]'
                      }`}
                    >
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-industrial truncate">
                          {p.name}
                        </div>
                        <div className="text-xs text-industrial-muted truncate mt-0.5">
                          {p.property_address || 'No address'}
                        </div>
                      </div>
                      {picked && (
                        <span className="flex-shrink-0 w-5 h-5 rounded-full bg-[var(--accent)] text-white flex items-center justify-center">
                          <Check size={12} strokeWidth={3} />
                        </span>
                      )}
                    </button>
                  );
                })
              )}
            </div>
          </div>
        ) : (
          <div className="p-5 grid gap-4">
            <div>
              <label className="block text-sm font-medium text-industrial mb-1.5">
                Project name{' '}
                <span className="text-[var(--accent)]">*</span>
              </label>
              <input
                autoFocus
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. Scottsdale strip retail scan"
                className="w-full px-3 py-2.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)]/50 transition-colors"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-industrial mb-1.5">
                Property address
                <span className="text-industrial-muted font-normal ml-1">
                  (optional)
                </span>
              </label>
              <input
                value={newAddress}
                onChange={(e) => setNewAddress(e.target.value)}
                placeholder="Link to a property"
                className="w-full px-3 py-2.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)]/50 transition-colors"
              />
            </div>
            <div className="px-3.5 py-3 rounded-lg bg-[var(--bg-secondary)] text-xs text-industrial-secondary leading-relaxed">
              <span className="font-semibold text-industrial">Tip</span> — your
              existing chat history stays. The shift is forward-looking: new
              messages benefit from project context and uploaded data.
            </div>
          </div>
        )}

        {promote.isError && (
          <p className="px-6 pb-1 text-xs text-[var(--color-error)]">
            Couldn&apos;t save the chat. Please try again.
          </p>
        )}

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-[var(--border-subtle)] bg-[var(--bg-secondary)]">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm font-medium text-industrial-secondary hover:bg-[var(--bg-tertiary)] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit || promote.isPending}
            className="px-4 py-2 rounded-lg text-sm font-semibold bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {promote.isPending
              ? 'Saving…'
              : mode === 'existing'
                ? 'Save to project'
                : 'Create & save'}
          </button>
        </div>
      </div>
    </div>
  );
}
