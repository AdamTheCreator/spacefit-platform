import { useState } from 'react';
import { FileText, MoreHorizontal, Archive, Trash2, RefreshCw } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import type { ParsedDocument } from '../../types/document';
import { documentKeys, fetchDocumentFile } from '../../hooks/useDocuments';

const TYPE_LABELS: Record<string, string> = {
  leasing_flyer: 'Leasing flyer',
  site_plan: 'Site plan',
  void_analysis: 'Void analysis',
  investment_memo: 'Inv. memo',
  offering_memorandum: 'Offering memo',
  loi: 'LOI',
  loan_document: 'Loan doc',
  comp_report: 'Comp report',
  other: 'Document',
};

function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return 'recently';
  const diffMs = Date.now() - then;
  if (diffMs < 0) return 'just now';
  const seconds = Math.round(diffMs / 1000);
  if (seconds < 45) return 'just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  const weeks = Math.round(days / 7);
  if (weeks < 5) return `${weeks}w ago`;
  const months = Math.round(days / 30);
  if (months < 12) return `${months}mo ago`;
  const years = Math.round(days / 365);
  return `${years}y ago`;
}

interface DocumentCardProps {
  document: ParsedDocument;
  onClick?: () => void;
  onArchive?: (doc: ParsedDocument) => void;
  onDelete?: (doc: ParsedDocument) => void;
  onReindex?: (doc: ParsedDocument) => void;
  isReindexing?: boolean;
}

export function DocumentCard({
  document,
  onClick,
  onArchive,
  onDelete,
  onReindex,
  isReindexing = false,
}: DocumentCardProps) {
  const [showMenu, setShowMenu] = useState(false);
  const queryClient = useQueryClient();
  const label = TYPE_LABELS[document.document_type] || 'Document';
  const confidence = document.confidence_score
    ? `${Math.round(document.confidence_score * 100)}% conf`
    : null;
  const isProcessing =
    document.status === 'pending' || document.status === 'processing';
  const isCompleted = document.status === 'completed';
  const hasActions = onArchive || onDelete || onReindex;
  const canPrefetch = onClick && document.status === 'completed';

  const stale =
    isCompleted &&
    (!document.indexed_at ||
      (document.processed_at
        ? document.indexed_at < document.processed_at
        : false));

  let freshnessTitle: string;
  if (!document.indexed_at) {
    freshnessTitle = 'Not yet indexed — re-index to make it searchable';
  } else if (stale) {
    freshnessTitle = 'Indexed before the last reprocess — re-index to refresh';
  } else {
    freshnessTitle = `Indexed ${formatRelativeTime(document.indexed_at)}`;
  }

  const handlePrefetch = () => {
    if (!canPrefetch) return;
    queryClient.prefetchQuery({
      queryKey: [...documentKeys.detail(document.id), 'file'],
      queryFn: () => fetchDocumentFile(document.id),
      staleTime: 5 * 60 * 1000,
    });
  };

  return (
    <div className="group relative">
      <button
        type="button"
        onClick={onClick}
        onMouseEnter={handlePrefetch}
        onFocus={handlePrefetch}
        className="relative w-full overflow-hidden rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-primary)] p-3 text-left transition-colors hover:border-[var(--accent)]/20 hover:bg-[var(--bg-secondary)]"
        title={onClick ? `Preview ${document.filename}` : document.filename}
      >
        {/* Subtle static accent bar at bottom while processing */}
        {isProcessing && (
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-[var(--border-subtle)]">
            <div className="h-full bg-[var(--accent)] opacity-60" />
          </div>
        )}
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex items-start gap-2">
            <FileText size={14} className="text-industrial-muted mt-0.5 flex-shrink-0" />
            <div className="min-w-0">
              <div className="text-sm font-medium text-industrial truncate pr-6">
                {document.filename}
              </div>
              <div className="mt-1 flex items-center gap-1.5 text-[11px] text-industrial-muted">
                <span>
                  {label}
                  {confidence ? `  ${confidence}` : ''}
                </span>
                {isCompleted && (
                  <span
                    title={freshnessTitle}
                    className="inline-flex items-center rounded-full px-1.5 py-[1px] text-[11px] leading-none"
                    style={
                      stale
                        ? {
                            color: 'var(--color-warning)',
                            backgroundColor: 'var(--bg-warning)',
                          }
                        : {
                            color: 'var(--color-success)',
                            backgroundColor: 'var(--bg-success)',
                          }
                    }
                  >
                    {stale ? 'Stale' : 'Fresh'}
                  </span>
                )}
              </div>
            </div>
          </div>
          {isProcessing && (
            <span className="text-[11px] text-[var(--accent)] font-medium whitespace-nowrap">
              Extracting...
            </span>
          )}
        </div>
      </button>

      {hasActions && (
        <div className="absolute right-2 top-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setShowMenu((c) => !c);
            }}
            className="rounded-lg p-1 text-industrial-muted opacity-0 group-hover:opacity-100 transition-opacity hover:bg-[var(--bg-tertiary)]"
          >
            <MoreHorizontal size={14} />
          </button>

          {showMenu && (
            <>
              <button
                type="button"
                className="fixed inset-0 z-10 cursor-default"
                onClick={() => setShowMenu(false)}
              />
              <div className="absolute right-0 z-20 mt-1 w-40 overflow-hidden rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] py-1 shadow-md">
                {onArchive && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowMenu(false);
                      onArchive(document);
                    }}
                    className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-industrial-secondary transition-colors hover:bg-[var(--bg-tertiary)]"
                  >
                    <Archive size={12} />
                    Archive
                  </button>
                )}
                {onReindex && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (isReindexing) return;
                      setShowMenu(false);
                      onReindex(document);
                    }}
                    disabled={isReindexing}
                    aria-disabled={isReindexing}
                    className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-industrial-secondary transition-colors hover:bg-[var(--bg-tertiary)] disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <RefreshCw size={12} />
                    {isReindexing ? 'Re-indexing…' : 'Re-index'}
                  </button>
                )}
                {onDelete && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowMenu(false);
                      onDelete(document);
                    }}
                    className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-[var(--color-error)] transition-colors hover:bg-[var(--bg-error)]"
                  >
                    <Trash2 size={12} />
                    Delete
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
