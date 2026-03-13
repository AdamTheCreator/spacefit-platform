import { useState, useCallback, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppLayout } from '../components/Layout';
import {
  useDocuments,
  useDeleteDocument,
  useReprocessDocument,
  useDocument,
  useDocumentFile,
  useStartAnalysis,
  useUploadWithProgress,
  useUploadStatusSync,
} from '../hooks/useDocuments';
import { useUploadStore } from '../stores/uploadStore';
import type { UploadItem, UploadStatus } from '../stores/uploadStore';
import { StartAnalysisModal } from '../components/Documents/StartAnalysisModal';
import type { AnalysisOptions } from '../components/Documents/StartAnalysisModal';
import { Button } from '../components/ui/Button';
import type { ParsedDocument, DocumentType, ExtractedFlyerData, ExtractedVoidData } from '../types/document';

const DOCUMENT_TYPE_LABELS: Record<DocumentType, string> = {
  leasing_flyer: 'Leasing Flyer',
  site_plan: 'Site Plan',
  void_analysis: 'Tenant Gap Analysis',
  investment_memo: 'Investment Memo',
  loan_document: 'Loan Document',
  comp_report: 'Comp Report',
  offering_memorandum: 'Offering Memorandum',
  loi: 'Letter of Intent',
  other: 'Other',
};

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-[var(--color-warning)]/10 text-[var(--color-warning)] border-[var(--color-warning)]/30',
  processing: 'bg-[var(--accent)]/10 text-[var(--accent)] border-[var(--accent)]/30',
  completed: 'bg-[var(--color-success)]/10 text-[var(--color-success)] border-[var(--color-success)]/30',
  failed: 'bg-[var(--color-error)]/10 text-[var(--color-error)] border-[var(--color-error)]/30',
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

interface DocumentCardProps {
  document: ParsedDocument;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  isSelected: boolean;
}

function DocumentCard({ document, onSelect, onDelete, isSelected }: DocumentCardProps) {
  return (
    <div
      onClick={() => onSelect(document.id)}
      className={`p-4 rounded-xl border cursor-pointer transition-all shadow-sm hover:shadow-md ${
        isSelected
          ? 'bg-[var(--accent)]/10 border-[var(--accent)] ring-1 ring-[var(--accent)]/20'
          : 'bg-[var(--bg-elevated)] border-[var(--border-subtle)] hover:border-[var(--border-default)]'
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          {/* File icon based on type */}
          <div className="w-10 h-10 bg-[var(--bg-tertiary)] border border-[var(--border-subtle)] rounded-lg flex items-center justify-center">
            {document.mime_type === 'application/pdf' ? (
              <svg className="w-5 h-5 text-[var(--color-error)]" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"
                  clipRule="evenodd"
                />
              </svg>
            ) : (
              <svg className="w-5 h-5 text-[var(--accent)]" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z"
                  clipRule="evenodd"
                />
              </svg>
            )}
          </div>

          <div>
            <h3 className="text-sm font-medium text-industrial truncate max-w-[200px]">
              {document.filename}
            </h3>
            <p className="text-xs text-industrial-muted mt-0.5">
              {formatFileSize(document.file_size)} • {formatDate(document.created_at)}
            </p>
          </div>
        </div>

        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete(document.id);
          }}
          className="p-1.5 rounded-lg text-industrial-muted hover:text-[var(--color-error)] hover:bg-[var(--bg-error)] transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
            />
          </svg>
        </button>
      </div>

      <div className="mt-3 flex items-center gap-2 flex-wrap">
        <span
          className={`px-2.5 py-1 text-[11px] font-medium rounded-full border ${
            STATUS_COLORS[document.status]
          }`}
        >
          {document.status === 'processing' && (
            <span className="inline-block w-1.5 h-1.5 mr-1.5 rounded-full bg-current animate-pulse" />
          )}
          {document.status.charAt(0).toUpperCase() + document.status.slice(1)}
        </span>
        <span className="px-2.5 py-1 text-[11px] font-medium rounded-full bg-[var(--bg-tertiary)] text-industrial-secondary border border-[var(--border-subtle)]">
          {DOCUMENT_TYPE_LABELS[document.document_type]}
        </span>
        {document.confidence_score && (
          <span className="px-2.5 py-1 text-[11px] font-medium rounded-full bg-[var(--accent)]/10 text-[var(--accent)] border border-[var(--accent)]/30">
            {Math.round(document.confidence_score * 100)}% confidence
          </span>
        )}
      </div>
    </div>
  );
}

interface UploadDropzoneProps {
  onUpload: (files: File[]) => void;
}

function UploadDropzone({ onUpload }: UploadDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropzoneRef = useRef<HTMLDivElement>(null);
  const dragCounterRef = useRef(0);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current++;
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDragging(true);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current--;
    if (dragCounterRef.current === 0) {
      setIsDragging(false);
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
      dragCounterRef.current = 0;

      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) {
        onUpload(files);
      }
    },
    [onUpload]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files ? Array.from(e.target.files) : [];
      if (files.length > 0) onUpload(files);
      if (fileInputRef.current) fileInputRef.current.value = '';
    },
    [onUpload]
  );

  return (
    <div
      ref={dropzoneRef}
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={() => fileInputRef.current?.click()}
      className={`relative p-6 border-2 border-dashed rounded-xl cursor-pointer transition-all ${
        isDragging
          ? 'border-[var(--accent)] bg-[var(--accent)]/10 scale-[1.02]'
          : 'border-[var(--border-default)] hover:border-[var(--accent)] bg-[var(--bg-tertiary)]'
      }`}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.png,.jpg,.jpeg,.gif,.webp"
        multiple
        onChange={handleFileSelect}
        className="hidden"
      />
      <div className="flex flex-col items-center text-center">
        <div className="w-12 h-12 bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl flex items-center justify-center mb-3">
          <svg
            className="w-6 h-6 text-industrial-muted"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
            />
          </svg>
        </div>
        <p className="text-sm font-medium text-industrial mb-0.5">
          Drop files here or click to upload
        </p>
        <p className="text-xs text-industrial-muted">
          PDF, PNG, JPG (max 50 MB)
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Upload Queue — renders below the drop zone
// ---------------------------------------------------------------------------

const UPLOAD_STATUS_CONFIG: Record<UploadStatus, { color: string; bgColor: string; borderColor: string }> = {
  uploading: {
    color: 'text-[var(--accent)]',
    bgColor: 'bg-[var(--accent)]',
    borderColor: 'border-[var(--accent)]/30',
  },
  processing: {
    color: 'text-[var(--accent)]',
    bgColor: 'bg-[var(--accent)]',
    borderColor: 'border-[var(--accent)]/30',
  },
  completed: {
    color: 'text-[var(--color-success)]',
    bgColor: 'bg-[var(--color-success)]',
    borderColor: 'border-[var(--color-success)]/30',
  },
  failed: {
    color: 'text-[var(--color-error)]',
    bgColor: 'bg-[var(--color-error)]',
    borderColor: 'border-[var(--color-error)]/30',
  },
};

function UploadQueueItem({
  item,
  onRetry,
  onDismiss,
}: {
  item: UploadItem;
  onRetry: (clientId: string) => void;
  onDismiss: (clientId: string) => void;
}) {
  const cfg = UPLOAD_STATUS_CONFIG[item.status];

  return (
    <div className={`p-3 rounded-lg border bg-[var(--bg-elevated)] ${cfg.borderColor} transition-all`}>
      {/* Top row: filename + actions */}
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2 min-w-0">
          {/* Status icon */}
          {item.status === 'uploading' && (
            <svg className={`w-4 h-4 flex-shrink-0 ${cfg.color} animate-spin`} fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          )}
          {item.status === 'processing' && (
            <div className="relative w-4 h-4 flex-shrink-0">
              <div className="w-4 h-4 rounded-full border-2 border-[var(--border-default)]" />
              <div className="absolute inset-0 rounded-full border-2 border-[var(--accent)] border-t-transparent animate-spin" />
            </div>
          )}
          {item.status === 'completed' && (
            <svg className={`w-4 h-4 flex-shrink-0 ${cfg.color}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          )}
          {item.status === 'failed' && (
            <svg className={`w-4 h-4 flex-shrink-0 ${cfg.color}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          )}

          <span className="text-xs font-medium text-industrial truncate">{item.fileName}</span>
          <span className="text-[10px] text-industrial-muted flex-shrink-0">{formatFileSize(item.fileSize)}</span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 flex-shrink-0">
          {item.status === 'failed' && (
            <button
              onClick={() => onRetry(item.clientId)}
              className="px-2 py-0.5 rounded text-[10px] font-medium text-[var(--accent)] hover:bg-[var(--accent)]/10 transition-colors"
            >
              Retry
            </button>
          )}
          {(item.status === 'completed' || item.status === 'failed') && (
            <button
              onClick={() => onDismiss(item.clientId)}
              className="p-0.5 rounded text-industrial-muted hover:text-industrial transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      {(item.status === 'uploading' || item.status === 'processing') && (
        <div className="h-1.5 rounded-full bg-[var(--bg-tertiary)] overflow-hidden">
          {item.status === 'uploading' ? (
            // Determinate bar
            <div
              className={`h-full rounded-full ${cfg.bgColor} transition-[width] duration-200 ease-out`}
              style={{ width: `${item.uploadProgress}%` }}
            />
          ) : (
            // Indeterminate bar — processing
            <div className="h-full w-full relative">
              <div
                className={`absolute inset-y-0 ${cfg.bgColor} rounded-full animate-[indeterminate_1.5s_ease-in-out_infinite]`}
                style={{ width: '40%' }}
              />
            </div>
          )}
        </div>
      )}

      {/* Status text */}
      <p className={`text-[10px] mt-1 ${item.status === 'failed' ? 'text-[var(--color-error)]' : 'text-industrial-muted'}`}>
        {item.status === 'failed' && item.errorMessage ? item.errorMessage : item.statusText}
      </p>
    </div>
  );
}

function UploadQueue({ onRetry }: { onRetry: (clientId: string) => void }) {
  const items = useUploadStore((s) => s.items);
  const removeItem = useUploadStore((s) => s.removeItem);
  const clearFinished = useUploadStore((s) => s.clearFinished);

  if (items.length === 0) return null;

  const hasFinished = items.some((i) => i.status === 'completed' || i.status === 'failed');

  return (
    <div className="mt-3 space-y-2">
      <div className="flex items-center justify-between px-1">
        <span className="text-[11px] font-medium text-industrial-muted uppercase tracking-wide">
          Upload Queue
        </span>
        {hasFinished && (
          <button
            onClick={clearFinished}
            className="text-[10px] text-industrial-muted hover:text-industrial transition-colors"
          >
            Clear finished
          </button>
        )}
      </div>
      {items.map((item) => (
        <UploadQueueItem
          key={item.clientId}
          item={item}
          onRetry={onRetry}
          onDismiss={removeItem}
        />
      ))}
    </div>
  );
}

interface DocumentDetailPanelProps {
  documentId: string;
}

function DocumentDetailPanel({ documentId }: DocumentDetailPanelProps) {
  const navigate = useNavigate();
  const { data: document, isLoading } = useDocument(documentId);
  const { data: fileUrl, isLoading: isFileLoading } = useDocumentFile(documentId);
  const [showPreview, setShowPreview] = useState(false);

  const startAnalysisMutation = useStartAnalysis();
  const reprocessMutation = useReprocessDocument();
  const [showAnalysisModal, setShowAnalysisModal] = useState(false);

  const handleViewDocument = useCallback(() => {
    if (fileUrl) {
      window.open(fileUrl, '_blank');
    }
  }, [fileUrl]);

  const handleDownload = useCallback(() => {
    if (fileUrl && document) {
      const link = window.document.createElement('a');
      link.href = fileUrl;
      link.download = document.filename;
      window.document.body.appendChild(link);
      link.click();
      window.document.body.removeChild(link);
    }
  }, [fileUrl, document]);

  const handleOpenAnalysisModal = useCallback(() => {
    setShowAnalysisModal(true);
  }, []);

  const handleConfirmAnalysis = useCallback(async (options: AnalysisOptions) => {
    if (!documentId) return;
    try {
      const result = await startAnalysisMutation.mutateAsync({
        documentId,
        analysisType: options.analysisType,
        tradeAreaMiles: options.tradeAreaMiles,
        notes: options.notes || undefined,
      });
      setShowAnalysisModal(false);
      // Navigate to chat with auto-kickoff flag
      navigate(`/chat/${result.session_id}`, {
        state: {
          initialMessage: 'Begin the analysis for this property.',
          documentId,
        },
      });
    } catch (error) {
      console.error('Failed to start analysis:', error);
    }
  }, [documentId, startAnalysisMutation, navigate]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="relative w-8 h-8">
          <div className="w-8 h-8 rounded-full border-2 border-[var(--border-default)]" />
          <div className="absolute inset-0 rounded-full border-2 border-[var(--accent)] border-t-transparent animate-spin" />
        </div>
      </div>
    );
  }

  if (!document) {
    return (
      <div className="text-center text-industrial-muted py-8 text-sm">Document not found</div>
    );
  }

  const renderFlyerData = (data: ExtractedFlyerData) => (
    <div className="space-y-6">
      {/* Property Info */}
      {data.property_info && (
        <div>
          <h4 className="text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-2">Property Information</h4>
          <div className="bg-[var(--bg-tertiary)] border border-[var(--border-subtle)] rounded-xl p-4 space-y-2">
            {data.property_info.name && (
              <p className="text-sm font-semibold text-industrial">{data.property_info.name}</p>
            )}
            {data.property_info.address && (
              <p className="text-xs text-industrial-secondary">
                {data.property_info.address}
                {data.property_info.city && `, ${data.property_info.city}`}
                {data.property_info.state && `, ${data.property_info.state}`}
                {data.property_info.zip_code && ` ${data.property_info.zip_code}`}
              </p>
            )}
            <div className="flex flex-wrap gap-2 mt-2">
              {data.property_info.total_sf && (
                <span className="px-2.5 py-1 bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-full text-[11px] font-medium text-industrial-secondary">
                  {data.property_info.total_sf.toLocaleString()} SF Total
                </span>
              )}
              {data.property_info.property_type && (
                <span className="px-2.5 py-1 bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-full text-[11px] font-medium text-industrial-secondary">
                  {data.property_info.property_type}
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Available Spaces */}
      {data.available_spaces && data.available_spaces.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-2">
            Available Spaces ({data.available_spaces.length})
          </h4>
          <div className="space-y-2">
            {data.available_spaces.map((space, index) => (
              <div key={space.suite_number || `space-${index}-${space.square_footage}`} className="bg-[var(--bg-tertiary)] border border-[var(--border-subtle)] rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-industrial">
                    {space.suite_number || `Space ${index + 1}`}
                  </span>
                  {space.square_footage && (
                    <span className="text-sm font-semibold text-[var(--color-success)]">
                      {space.square_footage.toLocaleString()} SF
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {space.asking_rent_psf && (
                    <span className="px-2 py-0.5 bg-[var(--bg-success)] text-[var(--color-success)] rounded-full text-[10px] font-medium">
                      ${space.asking_rent_psf}/SF {space.rent_type || ''}
                    </span>
                  )}
                  {space.is_endcap && (
                    <span className="px-2 py-0.5 bg-[var(--accent)]/10 text-[var(--accent)] rounded-full text-[10px] font-medium">
                      Endcap
                    </span>
                  )}
                  {space.has_drive_thru && (
                    <span className="px-2 py-0.5 bg-[var(--accent)]/10 text-[var(--accent)] rounded-full text-[10px] font-medium">
                      Drive-Thru
                    </span>
                  )}
                  {space.has_patio && (
                    <span className="px-2 py-0.5 bg-[var(--color-warning)]/10 text-[var(--color-warning)] rounded-full text-[10px] font-medium">
                      Patio
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Existing Tenants */}
      {data.existing_tenants && data.existing_tenants.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-2">
            Current Tenants ({data.existing_tenants.length})
          </h4>
          <div className="flex flex-wrap gap-2">
            {data.existing_tenants.map((tenant) => (
              <span
                key={tenant.name}
                className={`px-2.5 py-1 rounded-full text-[11px] font-medium ${
                  tenant.is_anchor
                    ? 'bg-[var(--accent)]/10 text-[var(--accent)]'
                    : 'bg-[var(--bg-secondary)] text-industrial-secondary border border-[var(--border-subtle)]'
                }`}
              >
                {tenant.name}
                {tenant.is_anchor && ' (Anchor)'}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Highlights */}
      {data.highlights && data.highlights.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-2">Highlights</h4>
          <ul className="space-y-1.5">
            {data.highlights.map((highlight) => (
              <li key={highlight} className="text-xs text-industrial-secondary flex items-start gap-2">
                <span className="text-[var(--color-success)] mt-0.5">•</span>
                {highlight}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );

  const renderVoidData = (data: ExtractedVoidData) => (
    <div className="space-y-6">
      {/* Summary */}
      <div className="bg-[var(--bg-tertiary)] border border-[var(--border-subtle)] rounded-xl p-4">
        <h4 className="text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-3">Analysis Summary</h4>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-2xl font-bold text-[var(--color-error)] tabular-nums">{data.summary?.total_voids || 0}</p>
            <p className="text-[11px] text-industrial-muted">Total Gaps</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-industrial tabular-nums">
              {data.summary?.total_categories_analyzed || 0}
            </p>
            <p className="text-[11px] text-industrial-muted">Categories Analyzed</p>
          </div>
        </div>
      </div>

      {/* High Priority Voids */}
      {data.summary?.high_priority_voids && data.summary.high_priority_voids.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-2">High Priority Opportunities</h4>
          <div className="space-y-2">
            {data.summary.high_priority_voids.map((void_name) => (
              <div
                key={void_name}
                className="flex items-center gap-2 p-3 rounded-lg bg-[var(--bg-error)] border border-[var(--color-error)]/20"
              >
                <span className="w-2 h-2 rounded-full bg-[var(--color-error)]" />
                <span className="text-sm text-industrial">{void_name}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Categories */}
      {data.categories && data.categories.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-2">Categories</h4>
          <div className="space-y-2">
            {data.categories.slice(0, 10).map((cat) => (
              <div key={cat.category_name} className="bg-[var(--bg-tertiary)] border border-[var(--border-subtle)] rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-industrial">{cat.category_name}</span>
                  {cat.is_void ? (
                    <span className="px-2.5 py-0.5 bg-[var(--bg-error)] text-[var(--color-error)] rounded-full text-[10px] font-medium">
                      Gap
                    </span>
                  ) : (
                    <span className="px-2.5 py-0.5 bg-[var(--bg-success)] text-[var(--color-success)] rounded-full text-[10px] font-medium">
                      Present
                    </span>
                  )}
                </div>
                {cat.void_opportunities && cat.void_opportunities.length > 0 && (
                  <p className="text-[11px] text-industrial-muted mt-1">
                    Opportunities: {cat.void_opportunities.join(', ')}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  // Build property address for analysis (memoized)
  const propertyAddress = useMemo(() => {
    if (!document?.extracted_data) return null;
    const data = document.extracted_data as ExtractedFlyerData;
    const info = data.property_info;
    if (!info) return null;

    const parts = [];
    if (info.address) parts.push(info.address);
    if (info.city) parts.push(info.city);
    if (info.state) parts.push(info.state);
    if (info.zip_code) parts.push(info.zip_code);
    return parts.length > 0 ? parts.join(', ') : null;
  }, [document?.extracted_data]);

  const canStartAnalysis = document.status === 'completed' &&
    (document.document_type === 'leasing_flyer' || document.document_type === 'site_plan') &&
    document.extracted_data;

  return (
    <div className="h-full overflow-y-auto p-5">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-base font-semibold text-industrial mb-2">{document.filename}</h3>
            <div className="flex items-center gap-2">
              <span
                className={`px-2.5 py-1 text-[11px] font-medium rounded-full border ${
                  STATUS_COLORS[document.status]
                }`}
              >
                {document.status.charAt(0).toUpperCase() + document.status.slice(1)}
              </span>
              <span className="text-xs text-industrial-muted">
                {DOCUMENT_TYPE_LABELS[document.document_type]}
              </span>
            </div>
          </div>

          {/* Start Analysis Button */}
          {canStartAnalysis && (
            <Button
              variant="primary"
              onClick={handleOpenAnalysisModal}
              iconLeft={
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              }
            >
              Start Analysis
            </Button>
          )}
        </div>

        {/* Property Address if available */}
        {propertyAddress && (
          <p className="text-xs text-industrial-muted mt-2">
            {propertyAddress}
          </p>
        )}

        {/* View Document Buttons */}
        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            variant="secondary"
            onClick={handleViewDocument}
            disabled={isFileLoading || !fileUrl}
            iconLeft={
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
            }
          >
            {isFileLoading ? 'Loading...' : 'View in New Tab'}
          </Button>
          <Button
            variant="secondary"
            onClick={handleDownload}
            disabled={isFileLoading || !fileUrl}
            iconLeft={
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
            }
          >
            Download
          </Button>
          <Button
            variant="secondary"
            onClick={() => setShowPreview(!showPreview)}
            disabled={isFileLoading || !fileUrl}
            iconLeft={
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d={showPreview ? "M19 9l-7 7-7-7" : "M9 5l7 7-7 7"} />
              </svg>
            }
          >
            {showPreview ? 'Hide Preview' : 'Show Preview'}
          </Button>
        </div>
      </div>

      {/* Document Preview */}
      {showPreview && fileUrl && (
        <div className="mb-6 overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-tertiary)]">
          {document.mime_type.startsWith('image/') ? (
            <img
              src={fileUrl}
              alt={document.filename}
              className="w-full h-auto max-h-[600px] object-contain"
            />
          ) : document.mime_type === 'application/pdf' ? (
            <iframe
              src={fileUrl}
              title={document.filename}
              className="w-full h-[600px] border-0"
            />
          ) : (
            <div className="p-8 text-center text-sm text-industrial-muted">
              Preview not available for this file type.
              <div className="mt-4">
                <Button variant="secondary" onClick={handleViewDocument}>
                  Open in New Tab
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Error message + retry */}
      {document.status === 'failed' && (
        <div className="mb-4 p-4 rounded-xl bg-[var(--bg-error)] border border-[var(--color-error)]/20">
          <p className="text-sm text-[var(--color-error)]">
            {document.error_message || 'Document processing failed.'}
          </p>
          <Button
            variant="secondary"
            size="sm"
            className="mt-3"
            onClick={() => reprocessMutation.mutate(document.id)}
            loading={reprocessMutation.isPending}
            iconLeft={
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            }
          >
            {reprocessMutation.isPending ? 'Reprocessing…' : 'Retry Processing'}
          </Button>
        </div>
      )}

      {/* Processing indicator */}
      {(document.status === 'pending' || document.status === 'processing') && (
        <div className="flex flex-col items-center justify-center py-12">
          <div className="relative w-10 h-10 mb-4">
            <div className="w-10 h-10 rounded-full border-2 border-[var(--border-default)]" />
            <div className="absolute inset-0 rounded-full border-2 border-[var(--accent)] border-t-transparent animate-spin" />
          </div>
          <p className="text-sm text-industrial-muted">
            {document.status === 'pending'
              ? 'Waiting to process...'
              : 'Analyzing document with AI...'}
          </p>
        </div>
      )}

      {/* Extracted Data */}
      {document.status === 'completed' && document.extracted_data && (
        <div>
          {document.document_type === 'leasing_flyer' &&
            renderFlyerData(document.extracted_data as ExtractedFlyerData)}
          {document.document_type === 'void_analysis' &&
            renderVoidData(document.extracted_data as ExtractedVoidData)}
          {document.document_type !== 'leasing_flyer' &&
            document.document_type !== 'void_analysis' && (
              <div className="bg-[var(--bg-tertiary)] border border-industrial p-4">
                <h4 className="label-technical mb-2">Raw Extracted Data</h4>
                <pre className="font-mono text-[10px] text-industrial-secondary overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(document.extracted_data, null, 2)}
                </pre>
              </div>
            )}
        </div>
      )}

      {/* Available Spaces from DB */}
      {document.available_spaces && document.available_spaces.length > 0 && (
        <div className="mt-6">
          <h4 className="text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-2">
            Saved Available Spaces ({document.available_spaces.length})
          </h4>
          <div className="space-y-2">
            {document.available_spaces.map((space) => (
              <div key={space.id} className="bg-[var(--bg-tertiary)] border border-[var(--border-subtle)] rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-industrial">
                    {space.suite_number || 'Unknown Suite'}
                  </span>
                  {space.square_footage && (
                    <span className="text-sm font-semibold text-[var(--color-success)]">
                      {space.square_footage.toLocaleString()} SF
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Start Analysis Modal */}
      <StartAnalysisModal
        isOpen={showAnalysisModal}
        onClose={() => setShowAnalysisModal(false)}
        onConfirm={handleConfirmAnalysis}
        isLoading={startAnalysisMutation.isPending}
        propertyName={(document.extracted_data as ExtractedFlyerData | null)?.property_info?.name}
        propertyAddress={propertyAddress}
        tenantCount={(document.extracted_data as ExtractedFlyerData | null)?.existing_tenants?.length}
        availableSpaceCount={(document.extracted_data as ExtractedFlyerData | null)?.available_spaces?.length}
        documentType={document.document_type}
      />
    </div>
  );
}

export function DocumentsPage() {
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const { data, isLoading } = useDocuments();
  const deleteMutation = useDeleteDocument();
  const { uploadFile } = useUploadWithProgress();
  const resetForRetry = useUploadStore((s) => s.resetForRetry);

  // Sync document processing status → upload store
  useUploadStatusSync(data);

  // Handle file selection from DropZone
  const handleUpload = useCallback(
    (files: File[]) => {
      for (const file of files) {
        // Fire-and-forget — the upload store tracks progress
        uploadFile(file).catch(() => {
          // Errors already tracked in the store via markFailed
        });
      }
    },
    [uploadFile],
  );

  // Retry a failed upload
  const handleRetry = useCallback(
    (clientId: string) => {
      const item = useUploadStore.getState().items.find((i) => i.clientId === clientId);
      if (!item) return;
      resetForRetry(clientId);
      // Re-upload the original file
      // Remove the old entry and create a fresh one
      useUploadStore.getState().removeItem(clientId);
      uploadFile(item.file).catch(() => {});
    },
    [uploadFile, resetForRetry],
  );

  const handleDelete = useCallback(
    async (id: string) => {
      if (confirm('Are you sure you want to delete this document?')) {
        await deleteMutation.mutateAsync(id);
        if (selectedDocumentId === id) {
          setSelectedDocumentId(null);
        }
      }
    },
    [deleteMutation, selectedDocumentId],
  );

  return (
    <AppLayout>
      <div className="h-full flex bg-[var(--bg-primary)]">
        {/* Left Panel - Document List */}
        <div className="w-96 flex-shrink-0 border-r border-[var(--border-subtle)] flex flex-col bg-[var(--bg-secondary)]">
          <div className="p-5 border-b border-[var(--border-subtle)]">
            <h1 className="text-lg font-semibold text-industrial mb-1">Documents</h1>
            <p className="text-sm text-industrial-muted">
              Upload leasing flyers, gap analyses, and investment memos
            </p>
          </div>

          {/* Drop zone + upload queue */}
          <div className="p-4 pb-2">
            <UploadDropzone onUpload={handleUpload} />
            <UploadQueue onRetry={handleRetry} />
          </div>

          {/* Document list */}
          <div className="flex-1 overflow-y-auto p-4 pt-2 space-y-3 scrollbar-industrial">
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <div className="relative w-6 h-6">
                  <div className="w-6 h-6 rounded-full border-2 border-[var(--border-default)]" />
                  <div className="absolute inset-0 rounded-full border-2 border-[var(--accent)] border-t-transparent animate-spin" />
                </div>
              </div>
            ) : data?.items.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-sm text-industrial-muted">No documents uploaded yet</p>
              </div>
            ) : (
              data?.items.map((doc) => (
                <DocumentCard
                  key={doc.id}
                  document={doc}
                  onSelect={setSelectedDocumentId}
                  onDelete={handleDelete}
                  isSelected={selectedDocumentId === doc.id}
                />
              ))
            )}
          </div>
        </div>

        {/* Right Panel - Document Details */}
        <div className="flex-1 bg-[var(--bg-elevated)]">
          {selectedDocumentId ? (
            <DocumentDetailPanel documentId={selectedDocumentId} />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center p-8">
              <div className="w-16 h-16 bg-[var(--bg-tertiary)] border border-[var(--border-subtle)] rounded-2xl flex items-center justify-center mb-4">
                <svg
                  className="w-8 h-8 text-industrial-muted"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
              </div>
              <h2 className="text-base font-semibold text-industrial mb-2">
                Select a document to view details
              </h2>
              <p className="text-sm text-industrial-muted max-w-md leading-relaxed">
                Upload a leasing flyer, gap analysis, or investment memo to extract
                property data, available spaces, and tenant information automatically.
              </p>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
