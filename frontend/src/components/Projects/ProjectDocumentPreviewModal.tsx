import { useCallback, useEffect } from 'react';
import { Download, ExternalLink, Loader2, X } from 'lucide-react';
import { useDocumentFile } from '../../hooks/useDocuments';
import type { ParsedDocument } from '../../types/document';

interface ProjectDocumentPreviewModalProps {
  previewDocument: ParsedDocument | null;
  isOpen: boolean;
  onClose: () => void;
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ProjectDocumentPreviewModal({
  previewDocument,
  isOpen,
  onClose,
}: ProjectDocumentPreviewModalProps) {
  const documentId = isOpen ? previewDocument?.id ?? null : null;
  const {
    data: fileUrl,
    isLoading,
    isError,
    error,
  } = useDocumentFile(documentId);

  useEffect(() => {
    if (!isOpen) return undefined;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    window.document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.document.body.style.overflow = '';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  const handleOpenNewTab = useCallback(() => {
    if (fileUrl) {
      window.open(fileUrl, '_blank', 'noopener,noreferrer');
    }
  }, [fileUrl]);

  const handleDownload = useCallback(() => {
    if (!fileUrl || !previewDocument) return;
    const link = window.document.createElement('a');
    link.href = fileUrl;
    link.download = previewDocument.filename;
    window.document.body.appendChild(link);
    link.click();
    window.document.body.removeChild(link);
  }, [fileUrl, previewDocument]);

  if (!isOpen || !previewDocument) return null;

  const isPdf = previewDocument.mime_type === 'application/pdf';
  const isImage = previewDocument.mime_type.startsWith('image/');
  const statusTone =
    previewDocument.status === 'completed'
      ? 'text-[var(--color-success)]'
      : previewDocument.status === 'failed'
      ? 'text-[var(--color-error)]'
      : 'text-[var(--accent)]';
  const confidence =
    previewDocument.confidence_score != null
      ? `${Math.round(previewDocument.confidence_score * 100)}% conf`
      : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="project-document-preview-title"
    >
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      <div className="relative flex h-[min(90vh,900px)] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] shadow-xl animate-scale-in">
        <div className="flex items-start justify-between gap-4 border-b border-[var(--border-subtle)] px-5 py-4">
          <div className="min-w-0">
            <h2
              id="project-document-preview-title"
              className="truncate text-base font-semibold text-industrial"
            >
              {previewDocument.filename}
            </h2>
            <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-industrial-muted">
              <span className={statusTone}>
                {previewDocument.status === 'completed'
                  ? 'Completed'
                  : previewDocument.status === 'failed'
                  ? 'Failed'
                  : 'Processing'}
              </span>
              {confidence && <span>{confidence}</span>}
              <span>{formatFileSize(previewDocument.file_size)}</span>
              <span>{previewDocument.mime_type}</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {fileUrl && (
              <>
                <button
                  type="button"
                  onClick={handleOpenNewTab}
                  className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-xs text-industrial-muted hover:text-industrial hover:bg-[var(--bg-tertiary)] transition-colors"
                >
                  <ExternalLink size={14} />
                  Open
                </button>
                <button
                  type="button"
                  onClick={handleDownload}
                  className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-xs text-industrial-muted hover:text-industrial hover:bg-[var(--bg-tertiary)] transition-colors"
                >
                  <Download size={14} />
                  Download
                </button>
              </>
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close preview"
              className="rounded-lg p-2 text-industrial-muted hover:text-industrial hover:bg-[var(--bg-tertiary)] transition-colors"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-hidden bg-[var(--bg-primary)]">
          {isLoading ? (
            <div className="flex h-full items-center justify-center">
              <div className="flex items-center gap-2 text-sm text-industrial-muted">
                <Loader2 size={16} className="animate-spin" />
                Loading preview...
              </div>
            </div>
          ) : isError ? (
            <div className="flex h-full items-center justify-center px-6 text-center">
              <div>
                <p className="text-sm font-medium text-industrial">
                  Failed to load file preview
                </p>
                <p className="mt-1 text-xs text-[var(--color-error)]">
                  {error instanceof Error ? error.message : 'Unknown error'}
                </p>
              </div>
            </div>
          ) : fileUrl && isPdf ? (
            <iframe
              src={fileUrl}
              title={previewDocument.filename}
              className="h-full w-full border-0"
            />
          ) : fileUrl && isImage ? (
            <div className="flex h-full items-center justify-center overflow-auto p-4">
              <img
                src={fileUrl}
                alt={previewDocument.filename}
                className="max-h-full max-w-full rounded-lg border border-[var(--border-subtle)] object-contain shadow-sm"
              />
            </div>
          ) : fileUrl ? (
            <div className="flex h-full items-center justify-center px-6 text-center">
              <div>
                <p className="text-sm font-medium text-industrial">
                  Preview not available for this file type
                </p>
                <p className="mt-1 text-xs text-industrial-muted">
                  Use Open or Download to inspect the original file.
                </p>
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center px-6 text-center">
              <div>
                <p className="text-sm font-medium text-industrial">
                  Preview unavailable
                </p>
                <p className="mt-1 text-xs text-industrial-muted">
                  The file is attached, but a preview URL could not be created.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
