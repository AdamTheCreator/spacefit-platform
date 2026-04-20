import { AlertTriangle, X } from 'lucide-react';
import type { Project } from '../../types/project';

interface DeleteProjectModalProps {
  project: Pick<Project, 'name' | 'document_count' | 'session_count'>;
  isDeleting?: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export function DeleteProjectModal({
  project,
  isDeleting = false,
  onClose,
  onConfirm,
}: DeleteProjectModalProps) {
  const hasDocuments = project.document_count > 0;
  const hasChats = project.session_count > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative w-full max-w-md mx-4 rounded-2xl border border-[var(--border-default)] bg-[var(--bg-elevated)] shadow-xl">
        <div className="flex items-center justify-between gap-3 border-b border-[var(--border-subtle)] px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--bg-error)] text-[var(--color-error)]">
              <AlertTriangle size={18} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-industrial">
                Delete project?
              </h2>
              <p className="text-xs text-industrial-muted">
                This action cannot be undone.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isDeleting}
            className="rounded-lg p-1.5 text-industrial-muted transition-colors hover:bg-[var(--bg-tertiary)]"
          >
            <X size={18} />
          </button>
        </div>

        <div className="space-y-4 px-6 py-5">
          <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-secondary)] px-4 py-3">
            <p className="text-xs uppercase tracking-[0.2em] text-industrial-muted">
              Project
            </p>
            <p className="mt-1 text-sm font-semibold text-industrial">
              {project.name}
            </p>
          </div>

          <div className="space-y-2 text-sm text-industrial-secondary">
            <p>
              Deleting this project will permanently remove it from Perigee.
            </p>
            <p>
              {hasDocuments
                ? `${project.document_count} attached document${project.document_count === 1 ? '' : 's'} will also be permanently deleted from the database and disk.`
                : 'This project does not have any attached documents to delete.'}
            </p>
            <p>
              {hasChats
                ? `${project.session_count} project chat${project.session_count === 1 ? '' : 's'} will stay in your chat history, but they will no longer belong to this project.`
                : 'There are no project chats attached to this project.'}
            </p>
          </div>

          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isDeleting}
              className="rounded-lg px-4 py-2 text-sm font-medium text-industrial-secondary transition-colors hover:bg-[var(--bg-tertiary)] disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={onConfirm}
              disabled={isDeleting}
              className="rounded-lg bg-[var(--color-error)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--color-error)]/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isDeleting ? 'Deleting...' : 'Delete project'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
