import { useState, useEffect, useCallback, useRef } from 'react';
import { X, Upload, FileSpreadsheet, Download, CheckCircle, AlertCircle } from 'lucide-react';
import { Button } from '../ui/Button';
import { useImportCustomers, type ImportResult } from '../../hooks/useCustomers';

interface ImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const ACCEPTED_TYPES = [
  'text/csv',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
];
const ACCEPTED_EXTENSIONS = ['.csv', '.xlsx', '.xls'];

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function downloadTemplate() {
  const headers = 'name,company_name,email,phone,address,city,state,zip_code';
  const example = 'John Smith,Acme Corp,john@acme.com,555-123-4567,123 Main St,Austin,TX,78701';
  const content = `${headers}\n${example}`;

  const blob = new Blob([content], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'customer_import_template.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function ImportModal({ isOpen, onClose, onSuccess }: ImportModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragCounterRef = useRef(0);

  const importMutation = useImportCustomers();

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setFile(null);
      setResult(null);
      setError(null);
      importMutation.reset();
    }
  }, [isOpen]);

  // Handle Escape key
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !importMutation.isPending) {
        onClose();
      }
    },
    [isOpen, importMutation.isPending, onClose],
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const validateFile = (f: File): string | null => {
    const ext = f.name.toLowerCase().slice(f.name.lastIndexOf('.'));
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      return 'Please upload a CSV or Excel file (.csv, .xlsx, .xls)';
    }
    if (f.size > MAX_FILE_SIZE) {
      return `File is too large. Maximum size is ${formatFileSize(MAX_FILE_SIZE)}`;
    }
    return null;
  };

  const handleFileSelect = (f: File) => {
    const validationError = validateFile(f);
    if (validationError) {
      setError(validationError);
      setFile(null);
      return;
    }
    setError(null);
    setFile(f);
    setResult(null);
  };

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

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    dragCounterRef.current = 0;

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileSelect(files[0]);
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleImport = async () => {
    if (!file) return;

    try {
      const importResult = await importMutation.mutateAsync(file);
      setResult(importResult);
      if (importResult.imported > 0) {
        onSuccess();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed');
    }
  };

  const handleClose = () => {
    if (!importMutation.isPending) {
      onClose();
    }
  };

  if (!isOpen) return null;

  const isComplete = result !== null;
  const hasErrors = result && result.failed > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className="relative bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-subtle)]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-[var(--accent)]/10 rounded-lg flex items-center justify-center">
              <Upload size={16} className="text-[var(--accent)]" />
            </div>
            <h2 className="font-mono text-sm font-semibold uppercase tracking-wide text-industrial">
              Import Customers
            </h2>
          </div>
          <button
            onClick={handleClose}
            disabled={importMutation.isPending}
            className="p-1.5 rounded-lg hover:bg-[var(--bg-tertiary)] text-industrial-muted hover:text-industrial transition-colors disabled:opacity-50"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-5">
          {!isComplete ? (
            <>
              {/* Download Template */}
              <div className="flex items-center justify-between p-3 bg-[var(--bg-tertiary)] rounded-lg border border-[var(--border-subtle)]">
                <div>
                  <p className="text-sm font-medium text-industrial">
                    Need a template?
                  </p>
                  <p className="text-xs text-industrial-muted">
                    Download a CSV with the correct column headers
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  iconLeft={<Download size={14} />}
                  onClick={downloadTemplate}
                >
                  Download
                </Button>
              </div>

              {/* Drop Zone */}
              <div
                onDragEnter={handleDragEnter}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`relative p-8 border-2 border-dashed rounded-xl cursor-pointer transition-all ${
                  isDragging
                    ? 'border-[var(--accent)] bg-[var(--accent)]/10 scale-[1.02]'
                    : 'border-[var(--border-default)] hover:border-[var(--accent)] bg-[var(--bg-tertiary)]'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={handleInputChange}
                  className="hidden"
                />
                <div className="flex flex-col items-center text-center">
                  <div className="w-12 h-12 bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl flex items-center justify-center mb-3">
                    <FileSpreadsheet size={24} className="text-industrial-muted" />
                  </div>
                  <p className="text-sm font-medium text-industrial mb-0.5">
                    Drop your file here or click to browse
                  </p>
                  <p className="text-xs text-industrial-muted">
                    CSV or Excel (.xlsx) — max 10 MB
                  </p>
                </div>
              </div>

              {/* Selected File */}
              {file && (
                <div className="flex items-center gap-3 p-3 bg-[var(--accent)]/10 rounded-lg border border-[var(--accent)]/30">
                  <FileSpreadsheet size={20} className="text-[var(--accent)]" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-industrial truncate">
                      {file.name}
                    </p>
                    <p className="text-xs text-industrial-muted">
                      {formatFileSize(file.size)}
                    </p>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setFile(null);
                    }}
                    className="p-1 rounded hover:bg-[var(--bg-tertiary)] text-industrial-muted hover:text-industrial transition-colors"
                  >
                    <X size={16} />
                  </button>
                </div>
              )}

              {/* Error */}
              {error && (
                <div className="flex items-start gap-3 p-3 bg-[var(--color-error)]/10 rounded-lg border border-[var(--color-error)]/30">
                  <AlertCircle size={18} className="text-[var(--color-error)] flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-[var(--color-error)]">{error}</p>
                </div>
              )}
            </>
          ) : (
            /* Results */
            <div className="space-y-4">
              {/* Success count */}
              {result.imported > 0 && (
                <div className="flex items-center gap-3 p-4 bg-[var(--color-success)]/10 rounded-lg border border-[var(--color-success)]/30">
                  <CheckCircle size={20} className="text-[var(--color-success)]" />
                  <p className="text-sm font-medium text-[var(--color-success)]">
                    {result.imported} customer{result.imported !== 1 ? 's' : ''} imported successfully
                  </p>
                </div>
              )}

              {/* Failed count and errors */}
              {hasErrors && (
                <div className="space-y-3">
                  <div className="flex items-center gap-3 p-4 bg-[var(--color-error)]/10 rounded-lg border border-[var(--color-error)]/30">
                    <AlertCircle size={20} className="text-[var(--color-error)]" />
                    <p className="text-sm font-medium text-[var(--color-error)]">
                      {result.failed} row{result.failed !== 1 ? 's' : ''} failed to import
                    </p>
                  </div>

                  {result.errors.length > 0 && (
                    <div className="max-h-40 overflow-y-auto rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-tertiary)]">
                      <ul className="p-3 space-y-1">
                        {result.errors.map((err, i) => (
                          <li
                            key={i}
                            className="text-xs text-industrial-muted font-mono"
                          >
                            {err}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* No records imported */}
              {result.imported === 0 && result.failed === 0 && (
                <div className="flex items-center gap-3 p-4 bg-[var(--color-warning)]/10 rounded-lg border border-[var(--color-warning)]/30">
                  <AlertCircle size={20} className="text-[var(--color-warning)]" />
                  <p className="text-sm font-medium text-[var(--color-warning)]">
                    No customers found in the file
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-[var(--border-subtle)] flex items-center justify-end gap-3">
          {!isComplete ? (
            <>
              <Button
                variant="ghost"
                onClick={handleClose}
                disabled={importMutation.isPending}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleImport}
                disabled={!file || importMutation.isPending}
                loading={importMutation.isPending}
                iconLeft={<Upload size={16} />}
              >
                Import
              </Button>
            </>
          ) : (
            <Button variant="primary" onClick={handleClose}>
              Done
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
