import { useState } from 'react';
import { FileText, MoreHorizontal, Archive, Trash2 } from 'lucide-react';
import type { ParsedDocument } from '../../types/document';

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

interface DocumentCardProps {
  document: ParsedDocument;
  onClick?: () => void;
  onArchive?: (doc: ParsedDocument) => void;
  onDelete?: (doc: ParsedDocument) => void;
}

export function DocumentCard({ document, onClick, onArchive, onDelete }: DocumentCardProps) {
  const [showMenu, setShowMenu] = useState(false);
  const label = TYPE_LABELS[document.document_type] || 'Document';
  const confidence = document.confidence_score
    ? `${Math.round(document.confidence_score * 100)}% conf`
    : null;
  const isProcessing =
    document.status === 'pending' || document.status === 'processing';
  const hasActions = onArchive || onDelete;

  return (
    <div className="group relative">
      <button
        type="button"
        onClick={onClick}
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
              <div className="mt-1 text-[11px] text-industrial-muted">
                {label}
                {confidence ? `  ${confidence}` : ''}
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
