import { useState, useCallback, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppLayout } from '../components/Layout';
import {
  useDocuments,
  useUploadDocument,
  useDeleteDocument,
  useDocument,
  useDocumentFile,
  usePropertyAnalysis,
  type PropertyAnalysisResult,
} from '../hooks/useDocuments';
import type { ParsedDocument, DocumentType, ExtractedFlyerData, ExtractedVoidData } from '../types/document';

const DOCUMENT_TYPE_LABELS: Record<DocumentType, string> = {
  leasing_flyer: 'Leasing Flyer',
  void_analysis: 'Void Analysis',
  investment_memo: 'Investment Memo',
  loan_document: 'Loan Document',
  comp_report: 'Comp Report',
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
      className={`p-4 border cursor-pointer transition-all ${
        isSelected
          ? 'bg-[var(--accent)]/10 border-[var(--accent)]'
          : 'bg-[var(--bg-tertiary)] border-industrial-subtle hover:border-industrial'
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          {/* File icon based on type */}
          <div className="w-10 h-10 bg-[var(--bg-secondary)] border border-industrial-subtle flex items-center justify-center">
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
            <h3 className="font-mono text-sm font-medium text-industrial truncate max-w-[200px]">
              {document.filename}
            </h3>
            <p className="font-mono text-[10px] text-industrial-muted">
              {formatFileSize(document.file_size)} • {formatDate(document.created_at)}
            </p>
          </div>
        </div>

        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete(document.id);
          }}
          className="p-1.5 text-industrial-muted hover:text-[var(--color-error)] hover:bg-[var(--color-error)]/10 transition-colors"
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

      <div className="mt-3 flex items-center gap-2">
        <span
          className={`px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide border ${
            STATUS_COLORS[document.status]
          }`}
        >
          {document.status === 'processing' && (
            <span className="inline-block w-1.5 h-1.5 mr-1 bg-current animate-pulse" />
          )}
          {document.status}
        </span>
        <span className="px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide bg-[var(--bg-secondary)] text-industrial-secondary border border-industrial-subtle">
          {DOCUMENT_TYPE_LABELS[document.document_type]}
        </span>
        {document.confidence_score && (
          <span className="px-2 py-0.5 font-mono text-[10px] bg-[var(--accent)]/10 text-[var(--accent)] border border-[var(--accent)]/30">
            {Math.round(document.confidence_score * 100)}% confidence
          </span>
        )}
      </div>
    </div>
  );
}

interface UploadDropzoneProps {
  onUpload: (files: File[]) => void;
  isUploading: boolean;
}

function UploadDropzone({ onUpload, isUploading }: UploadDropzoneProps) {
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
      onUpload(files);
      // Reset input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
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
      className={`relative p-8 border-2 border-dashed cursor-pointer transition-all ${
        isDragging
          ? 'border-[var(--accent)] bg-[var(--accent)]/10'
          : 'border-industrial hover:border-industrial-subtle bg-[var(--bg-tertiary)]'
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
        {isUploading ? (
          <>
            <div className="relative w-12 h-12 mb-4">
              <div className="w-12 h-12 border border-industrial" />
              <div className="absolute inset-0 border-t border-[var(--accent)] animate-spin" />
            </div>
            <p className="font-mono text-sm text-industrial">Uploading...</p>
          </>
        ) : (
          <>
            <div className="w-12 h-12 bg-[var(--bg-secondary)] border border-industrial-subtle flex items-center justify-center mb-4">
              <svg
                className="w-6 h-6 text-industrial-muted"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </svg>
            </div>
            <p className="font-mono text-sm text-industrial mb-1">
              Drop files here or click to upload
            </p>
            <p className="font-mono text-xs text-industrial-muted">
              Supports PDF, PNG, JPG (max 50MB)
            </p>
          </>
        )}
      </div>
    </div>
  );
}

interface DocumentDetailPanelProps {
  documentId: string;
  onStartAnalysis: (document: ParsedDocument) => void;
}

function DocumentDetailPanel({ documentId, onStartAnalysis: _onStartAnalysis }: DocumentDetailPanelProps) {
  const { data: document, isLoading } = useDocument(documentId);
  const { data: fileUrl, isLoading: isFileLoading } = useDocumentFile(documentId);
  const [showPreview, setShowPreview] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<PropertyAnalysisResult | null>(null);
  const [showAnalysis, setShowAnalysis] = useState(false);

  const analysisMutation = usePropertyAnalysis();

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

  const handleRunAnalysis = useCallback(async () => {
    if (!documentId) return;

    try {
      const result = await analysisMutation.mutateAsync({
        documentId,
        includeDemographics: true,
        includeCompetitors: true,
        includeVoidAnalysis: true,
        radiusMiles: 3.0,
      });
      setAnalysisResult(result);
      setShowAnalysis(true);
    } catch (error) {
      console.error('Analysis failed:', error);
    }
  }, [documentId, analysisMutation]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!document) {
    return (
      <div className="text-center text-gray-400 py-8">Document not found</div>
    );
  }

  const renderFlyerData = (data: ExtractedFlyerData) => (
    <div className="space-y-6">
      {/* Property Info */}
      {data.property_info && (
        <div>
          <h4 className="text-sm font-medium text-gray-400 mb-2">Property Information</h4>
          <div className="bg-gray-800 rounded-lg p-4 space-y-2">
            {data.property_info.name && (
              <p className="text-white font-medium">{data.property_info.name}</p>
            )}
            {data.property_info.address && (
              <p className="text-gray-300 text-sm">
                {data.property_info.address}
                {data.property_info.city && `, ${data.property_info.city}`}
                {data.property_info.state && `, ${data.property_info.state}`}
                {data.property_info.zip_code && ` ${data.property_info.zip_code}`}
              </p>
            )}
            <div className="flex flex-wrap gap-2 mt-2">
              {data.property_info.total_sf && (
                <span className="px-2 py-1 bg-gray-700 rounded text-xs text-gray-300">
                  {data.property_info.total_sf.toLocaleString()} SF Total
                </span>
              )}
              {data.property_info.property_type && (
                <span className="px-2 py-1 bg-gray-700 rounded text-xs text-gray-300 capitalize">
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
          <h4 className="text-sm font-medium text-gray-400 mb-2">
            Available Spaces ({data.available_spaces.length})
          </h4>
          <div className="space-y-2">
            {data.available_spaces.map((space, index) => (
              <div key={space.suite_number || `space-${index}-${space.square_footage}`} className="bg-gray-800 rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <span className="text-white font-medium">
                    {space.suite_number || `Space ${index + 1}`}
                  </span>
                  {space.square_footage && (
                    <span className="text-green-400 font-medium">
                      {space.square_footage.toLocaleString()} SF
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {space.asking_rent_psf && (
                    <span className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-xs">
                      ${space.asking_rent_psf}/SF {space.rent_type || ''}
                    </span>
                  )}
                  {space.is_endcap && (
                    <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded text-xs">
                      Endcap
                    </span>
                  )}
                  {space.has_drive_thru && (
                    <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded text-xs">
                      Drive-Thru
                    </span>
                  )}
                  {space.has_patio && (
                    <span className="px-2 py-0.5 bg-orange-500/20 text-orange-400 rounded text-xs">
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
          <h4 className="text-sm font-medium text-gray-400 mb-2">
            Current Tenants ({data.existing_tenants.length})
          </h4>
          <div className="flex flex-wrap gap-2">
            {data.existing_tenants.map((tenant) => (
              <span
                key={tenant.name}
                className={`px-2 py-1 rounded text-xs ${
                  tenant.is_anchor
                    ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                    : 'bg-gray-700 text-gray-300'
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
          <h4 className="text-sm font-medium text-gray-400 mb-2">Highlights</h4>
          <ul className="space-y-1">
            {data.highlights.map((highlight) => (
              <li key={highlight} className="text-sm text-gray-300 flex items-start gap-2">
                <span className="text-green-400 mt-1">•</span>
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
      <div className="bg-gray-800 rounded-lg p-4">
        <h4 className="text-sm font-medium text-gray-400 mb-2">Analysis Summary</h4>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-2xl font-bold text-red-400">{data.summary?.total_voids || 0}</p>
            <p className="text-xs text-gray-400">Total Voids</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-white">
              {data.summary?.total_categories_analyzed || 0}
            </p>
            <p className="text-xs text-gray-400">Categories Analyzed</p>
          </div>
        </div>
      </div>

      {/* High Priority Voids */}
      {data.summary?.high_priority_voids && data.summary.high_priority_voids.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-400 mb-2">High Priority Opportunities</h4>
          <div className="space-y-2">
            {data.summary.high_priority_voids.map((void_name) => (
              <div
                key={void_name}
                className="flex items-center gap-2 p-2 bg-red-500/10 border border-red-500/30 rounded-lg"
              >
                <span className="w-2 h-2 rounded-full bg-red-500" />
                <span className="text-sm text-white">{void_name}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Categories */}
      {data.categories && data.categories.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-400 mb-2">Categories</h4>
          <div className="space-y-2">
            {data.categories.slice(0, 10).map((cat) => (
              <div key={cat.category_name} className="bg-gray-800 rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <span className="text-white font-medium">{cat.category_name}</span>
                  {cat.is_void ? (
                    <span className="px-2 py-0.5 bg-red-500/20 text-red-400 rounded text-xs">
                      VOID
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-xs">
                      Present
                    </span>
                  )}
                </div>
                {cat.void_opportunities && cat.void_opportunities.length > 0 && (
                  <p className="text-xs text-gray-400 mt-1">
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
    document.document_type === 'leasing_flyer' &&
    document.extracted_data;

  return (
    <div className="h-full overflow-y-auto p-4">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white mb-1">{document.filename}</h3>
            <div className="flex items-center gap-2">
              <span
                className={`px-2 py-0.5 text-xs rounded-full border ${
                  STATUS_COLORS[document.status]
                }`}
              >
                {document.status}
              </span>
              <span className="text-sm text-gray-400">
                {DOCUMENT_TYPE_LABELS[document.document_type]}
              </span>
            </div>
          </div>

          {/* Run Analysis Button */}
          {canStartAnalysis && (
            <button
              onClick={handleRunAnalysis}
              disabled={analysisMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-600 to-purple-600
                       hover:from-indigo-500 hover:to-purple-500 text-white text-sm font-medium
                       rounded-lg transition-all shadow-lg shadow-indigo-500/25 disabled:opacity-50"
            >
              {analysisMutation.isPending ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                  Run Void Analysis
                </>
              )}
            </button>
          )}
        </div>

        {/* Property Address if available */}
        {propertyAddress && (
          <p className="text-sm text-gray-400 mt-2">
            {propertyAddress}
          </p>
        )}

        {/* View Document Buttons */}
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            onClick={handleViewDocument}
            disabled={isFileLoading || !fileUrl}
            className="flex items-center gap-2 px-3 py-1.5 bg-gray-700 hover:bg-gray-600
                     text-gray-200 text-sm rounded-lg transition-colors disabled:opacity-50"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
            {isFileLoading ? 'Loading...' : 'View in New Tab'}
          </button>
          <button
            onClick={handleDownload}
            disabled={isFileLoading || !fileUrl}
            className="flex items-center gap-2 px-3 py-1.5 bg-gray-700 hover:bg-gray-600
                     text-gray-200 text-sm rounded-lg transition-colors disabled:opacity-50"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Download
          </button>
          <button
            onClick={() => setShowPreview(!showPreview)}
            disabled={isFileLoading || !fileUrl}
            className="flex items-center gap-2 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500
                     text-white text-sm rounded-lg transition-colors disabled:opacity-50"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d={showPreview ? "M19 9l-7 7-7-7" : "M9 5l7 7-7 7"} />
            </svg>
            {showPreview ? 'Hide Preview' : 'Show Preview'}
          </button>
        </div>
      </div>

      {/* Document Preview */}
      {showPreview && fileUrl && (
        <div className="mb-6 rounded-lg overflow-hidden border border-gray-700 bg-gray-800">
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
            <div className="p-8 text-center text-gray-400">
              Preview not available for this file type.
              <button
                onClick={handleViewDocument}
                className="block mx-auto mt-4 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg"
              >
                Open in New Tab
              </button>
            </div>
          )}
        </div>
      )}

      {/* Analysis Results */}
      {showAnalysis && analysisResult && (
        <div className="mb-6 space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-lg font-semibold text-white flex items-center gap-2">
              <svg className="w-5 h-5 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              Property Analysis Results
            </h4>
            <button
              onClick={() => setShowAnalysis(false)}
              className="text-gray-400 hover:text-white transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Location Info */}
          {analysisResult.property_address && (
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <svg className="w-4 h-4 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                <span className="text-sm font-medium text-gray-400">Geocoded Location</span>
              </div>
              <p className="text-white">{analysisResult.property_address}</p>
              {analysisResult.latitude && analysisResult.longitude && (
                <p className="text-xs text-gray-500 mt-1">
                  {analysisResult.latitude.toFixed(6)}, {analysisResult.longitude.toFixed(6)}
                </p>
              )}
            </div>
          )}

          {/* Demographics */}
          {analysisResult.demographics && (
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <svg className="w-4 h-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
                <span className="text-sm font-medium text-gray-400">Trade Area Demographics</span>
              </div>
              {(() => {
                const demo = analysisResult.demographics as Record<string, number | null>;
                return (
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    {demo.population != null && (
                      <div className="bg-gray-700/50 rounded-lg p-3">
                        <p className="text-lg font-bold text-white">
                          {demo.population.toLocaleString()}
                        </p>
                        <p className="text-xs text-gray-400">Population</p>
                      </div>
                    )}
                    {demo.households != null && (
                      <div className="bg-gray-700/50 rounded-lg p-3">
                        <p className="text-lg font-bold text-white">
                          {demo.households.toLocaleString()}
                        </p>
                        <p className="text-xs text-gray-400">Households</p>
                      </div>
                    )}
                    {demo.median_income != null && (
                      <div className="bg-gray-700/50 rounded-lg p-3">
                        <p className="text-lg font-bold text-green-400">
                          ${demo.median_income.toLocaleString()}
                        </p>
                        <p className="text-xs text-gray-400">Median Income</p>
                      </div>
                    )}
                    {demo.median_age != null && (
                      <div className="bg-gray-700/50 rounded-lg p-3">
                        <p className="text-lg font-bold text-white">
                          {demo.median_age.toFixed(1)}
                        </p>
                        <p className="text-xs text-gray-400">Median Age</p>
                      </div>
                    )}
                    {demo.bachelors_plus_pct != null && (
                      <div className="bg-gray-700/50 rounded-lg p-3">
                        <p className="text-lg font-bold text-white">
                          {demo.bachelors_plus_pct.toFixed(1)}%
                        </p>
                        <p className="text-xs text-gray-400">College Educated</p>
                      </div>
                    )}
                    {demo.owner_occupied_pct != null && (
                      <div className="bg-gray-700/50 rounded-lg p-3">
                        <p className="text-lg font-bold text-white">
                          {demo.owner_occupied_pct.toFixed(1)}%
                        </p>
                        <p className="text-xs text-gray-400">Owner Occupied</p>
                      </div>
                    )}
                  </div>
                );
              })()}
            </div>
          )}

          {/* Competitors */}
          {analysisResult.competitors && analysisResult.competitors.length > 0 && (
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                  </svg>
                  <span className="text-sm font-medium text-gray-400">Nearby Competitors</span>
                </div>
                <span className="text-xs text-gray-500">{analysisResult.competitors.length} found</span>
              </div>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {analysisResult.competitors.slice(0, 10).map((competitor) => (
                  <div key={competitor.name} className="flex items-center justify-between p-2 bg-gray-700/50 rounded">
                    <div>
                      <p className="text-sm text-white">{competitor.name}</p>
                      <p className="text-xs text-gray-400">{competitor.category}</p>
                    </div>
                    {competitor.rating && (
                      <div className="flex items-center gap-1">
                        <svg className="w-3 h-3 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                        <span className="text-xs text-gray-300">{competitor.rating}</span>
                      </div>
                    )}
                  </div>
                ))}
                {analysisResult.competitors.length > 10 && (
                  <p className="text-xs text-gray-500 text-center pt-2">
                    +{analysisResult.competitors.length - 10} more competitors
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Void Analysis */}
          {analysisResult.void_analysis && (
            <div className="bg-gradient-to-br from-indigo-900/30 to-purple-900/30 rounded-lg p-4 border border-indigo-500/30">
              <div className="flex items-center gap-2 mb-3">
                <svg className="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
                <span className="text-sm font-medium text-indigo-300">Void Analysis Results</span>
              </div>

              {/* Property Summary */}
              {analysisResult.void_analysis.property_summary && (
                <p className="text-sm text-gray-300 mb-4 italic">
                  {analysisResult.void_analysis.property_summary}
                </p>
              )}

              {/* Summary Stats */}
              {analysisResult.void_analysis.summary && (
                <div className="grid grid-cols-3 gap-3 mb-4">
                  <div className="bg-gray-800/50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-red-400">
                      {analysisResult.void_analysis.summary.total_voids || 0}
                    </p>
                    <p className="text-xs text-gray-400">Voids Found</p>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-yellow-400">
                      {analysisResult.void_analysis.summary.high_priority?.length || 0}
                    </p>
                    <p className="text-xs text-gray-400">High Priority</p>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-green-400">
                      {analysisResult.void_analysis.summary.well_served?.length || 0}
                    </p>
                    <p className="text-xs text-gray-400">Well Served</p>
                  </div>
                </div>
              )}

              {/* High Priority Voids */}
              {analysisResult.void_analysis.summary?.high_priority &&
               analysisResult.void_analysis.summary.high_priority.length > 0 && (
                <div className="mb-4">
                  <h5 className="text-sm font-medium text-red-400 mb-2">High Priority Opportunities</h5>
                  <div className="space-y-1">
                    {analysisResult.void_analysis.summary.high_priority.map((item) => (
                      <div key={item} className="flex items-center gap-2 p-2 bg-red-500/10 border border-red-500/20 rounded">
                        <span className="w-2 h-2 rounded-full bg-red-500" />
                        <span className="text-sm text-white">{item}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Categories with Details */}
              {analysisResult.void_analysis.categories && analysisResult.void_analysis.categories.length > 0 && (
                <div>
                  <h5 className="text-sm font-medium text-gray-400 mb-2">Category Breakdown</h5>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {analysisResult.void_analysis.categories
                      .filter(cat => cat.is_void)
                      .slice(0, 8)
                      .map((cat) => (
                      <div key={cat.category_name} className="bg-gray-800/50 rounded-lg p-3">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-white font-medium">{cat.category_name}</span>
                          <div className="flex items-center gap-2">
                            <span className={`px-2 py-0.5 text-xs rounded ${
                              cat.priority === 'high'
                                ? 'bg-red-500/20 text-red-400'
                                : cat.priority === 'medium'
                                ? 'bg-yellow-500/20 text-yellow-400'
                                : 'bg-gray-500/20 text-gray-400'
                            }`}>
                              {cat.priority}
                            </span>
                            <span className="text-xs text-indigo-400">
                              {Math.round(cat.match_score * 100)}% match
                            </span>
                          </div>
                        </div>
                        {cat.rationale && (
                          <p className="text-xs text-gray-400 mt-1">{cat.rationale}</p>
                        )}
                        {cat.suggested_tenants && cat.suggested_tenants.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {cat.suggested_tenants.slice(0, 4).map((tenant, j) => (
                              <span key={j} className="px-2 py-0.5 bg-indigo-500/20 text-indigo-300 text-xs rounded">
                                {tenant}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Key Recommendation */}
              {analysisResult.void_analysis.summary?.key_recommendation && (
                <div className="mt-4 p-3 bg-indigo-500/20 border border-indigo-500/30 rounded-lg">
                  <p className="text-sm font-medium text-indigo-300 mb-1">Key Recommendation</p>
                  <p className="text-sm text-white">{analysisResult.void_analysis.summary.key_recommendation}</p>
                </div>
              )}
            </div>
          )}

          {/* Analysis Errors */}
          {analysisResult.errors && analysisResult.errors.length > 0 && (
            <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <svg className="w-4 h-4 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span className="text-sm font-medium text-yellow-400">Partial Results</span>
              </div>
              <ul className="space-y-1">
                {analysisResult.errors.map((error, i) => (
                  <li key={i} className="text-xs text-yellow-300">{error}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Error message */}
      {document.error_message && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
          <p className="text-sm text-red-400">{document.error_message}</p>
        </div>
      )}

      {/* Processing indicator */}
      {(document.status === 'pending' || document.status === 'processing') && (
        <div className="flex flex-col items-center justify-center py-12">
          <div className="w-10 h-10 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4" />
          <p className="text-gray-400">
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
              <div className="bg-gray-800 rounded-lg p-4">
                <h4 className="text-sm font-medium text-gray-400 mb-2">Raw Extracted Data</h4>
                <pre className="text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(document.extracted_data, null, 2)}
                </pre>
              </div>
            )}
        </div>
      )}

      {/* Available Spaces from DB */}
      {document.available_spaces && document.available_spaces.length > 0 && (
        <div className="mt-6">
          <h4 className="text-sm font-medium text-gray-400 mb-2">
            Saved Available Spaces ({document.available_spaces.length})
          </h4>
          <div className="space-y-2">
            {document.available_spaces.map((space) => (
              <div key={space.id} className="bg-gray-800 rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <span className="text-white font-medium">
                    {space.suite_number || 'Unknown Suite'}
                  </span>
                  {space.square_footage && (
                    <span className="text-green-400">
                      {space.square_footage.toLocaleString()} SF
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function DocumentsPage() {
  const navigate = useNavigate();
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const { data, isLoading } = useDocuments();
  const uploadMutation = useUploadDocument();
  const deleteMutation = useDeleteDocument();
  const handleStartAnalysis = useCallback(
    (document: ParsedDocument) => {
      // Extract property address from document data
      const extractedData = document.extracted_data as ExtractedFlyerData | null;
      const propertyInfo = extractedData?.property_info;

      let propertyAddress = '';
      if (propertyInfo) {
        const parts = [];
        if (propertyInfo.name) parts.push(propertyInfo.name);
        if (propertyInfo.address) parts.push(propertyInfo.address);
        if (propertyInfo.city) parts.push(propertyInfo.city);
        if (propertyInfo.state) parts.push(propertyInfo.state);
        propertyAddress = parts.filter(Boolean).join(', ');
      }

      // Build context about the property
      const availableSpaces = extractedData?.available_spaces || [];
      const existingTenants = extractedData?.existing_tenants || [];

      // Create initial message with document context
      const contextMessage = `I've uploaded a leasing flyer for ${propertyAddress || 'a property'}.

Here's what I found:
${availableSpaces.length > 0 ? `- ${availableSpaces.length} available space(s) totaling ${availableSpaces.reduce((sum, s) => sum + (s.square_footage || 0), 0).toLocaleString()} SF` : ''}
${existingTenants.length > 0 ? `- ${existingTenants.length} existing tenant(s) including ${existingTenants.slice(0, 3).map(t => t.name).join(', ')}${existingTenants.length > 3 ? '...' : ''}` : ''}

Please run a void analysis on this property to identify potential tenant opportunities. I want to find tenants we can reach out to about the available space.`;

      // Navigate to chat with initial message in state
      navigate('/chat', {
        state: {
          initialMessage: contextMessage,
          documentId: document.id,
        },
      });
    },
    [navigate]
  );

  const handleUpload = useCallback(
    async (files: File[]) => {
      for (const file of files) {
        try {
          await uploadMutation.mutateAsync({ file });
        } catch (error) {
          console.error('Upload failed:', error);
        }
      }
    },
    [uploadMutation]
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
    [deleteMutation, selectedDocumentId]
  );

  return (
    <AppLayout>
      <div className="h-full flex bg-industrial">
        {/* Left Panel - Document List */}
        <div className="w-96 flex-shrink-0 border-r border-industrial flex flex-col">
          <div className="p-4 border-b border-industrial">
            <h1 className="font-mono text-lg font-bold tracking-tight text-industrial mb-1">Documents</h1>
            <p className="font-mono text-xs text-industrial-muted">
              Upload leasing flyers, void analyses, and investment memos
            </p>
          </div>

          <div className="p-4">
            <UploadDropzone
              onUpload={handleUpload}
              isUploading={uploadMutation.isPending}
            />
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-industrial">
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <div className="relative w-6 h-6">
                  <div className="w-6 h-6 border border-industrial" />
                  <div className="absolute inset-0 border-t border-[var(--accent)] animate-spin" />
                </div>
              </div>
            ) : data?.items.length === 0 ? (
              <div className="text-center py-8">
                <p className="font-mono text-xs text-industrial-muted">No documents uploaded yet</p>
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
            <DocumentDetailPanel
              documentId={selectedDocumentId}
              onStartAnalysis={handleStartAnalysis}
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center p-8">
              <div className="w-16 h-16 bg-[var(--bg-tertiary)] border border-industrial-subtle flex items-center justify-center mb-4">
                <svg
                  className="w-8 h-8 text-industrial-muted"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
              </div>
              <h2 className="font-mono text-sm font-semibold uppercase tracking-wide text-industrial mb-2">
                Select a document to view details
              </h2>
              <p className="font-mono text-xs text-industrial-muted max-w-md">
                Upload a leasing flyer, void analysis, or investment memo to extract
                property data, available spaces, and tenant information automatically.
              </p>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
