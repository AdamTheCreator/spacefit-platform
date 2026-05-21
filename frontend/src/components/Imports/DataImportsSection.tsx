import { useCallback, useRef, useState, type DragEvent } from 'react';
import {
  Upload,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Building2,
  Users,
  BarChart3,
} from 'lucide-react';
import {
  useImportUpload,
  detectImportSource,
  type ImportSource,
} from '../../hooks/useImportUpload';

const SOURCE_META: Record<
  ImportSource,
  { name: string; icon: React.ReactNode; accept: string; fileType: string; hint: string }
> = {
  costar: {
    name: 'CoStar',
    icon: <Building2 size={14} className="text-purple-400" />,
    accept: '.csv,.tsv,.txt',
    fileType: 'CSV',
    hint: 'Lease comps, tenant rosters',
  },
  placer: {
    name: 'Placer.ai',
    icon: <Users size={14} className="text-green-400" />,
    accept: '.pdf',
    fileType: 'PDF',
    hint: 'Foot traffic + demographics',
  },
  siteusa: {
    name: 'SiteUSA',
    icon: <BarChart3 size={14} className="text-blue-400" />,
    accept: '.csv,.tsv,.txt',
    fileType: 'CSV',
    hint: 'Vehicle traffic counts',
  },
};

interface DataImportsSectionProps {
  projectId?: string;
  onUploadComplete?: () => void;
  defaultOpen?: boolean;
}

export function DataImportsSection({
  projectId,
  onUploadComplete,
  defaultOpen = false,
}: DataImportsSectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  const [selectedSource, setSelectedSource] = useState<ImportSource>('costar');
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { state, upload, reset } = useImportUpload(projectId);

  const handleFile = useCallback(
    (file: File) => {
      // Auto-detect source by extension, but honor explicit selection
      // when the user picked one that doesn't conflict.
      const detected = detectImportSource(file);
      const source: ImportSource =
        // If user picked siteusa and file is a CSV, respect it (both CoStar
        // and SiteUSA accept CSV — extension alone can't disambiguate).
        selectedSource !== 'costar' || detected === 'placer'
          ? selectedSource
          : detected;
      upload(file, source, onUploadComplete);
    },
    [upload, selectedSource, onUploadComplete],
  );

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const activeJobs = (Object.entries(state) as [ImportSource, typeof state.costar][])
    .filter(([, s]) => s.status !== 'idle');

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="w-full flex items-center justify-between text-[11px] font-bold text-industrial-muted uppercase tracking-widest mb-2 hover:text-industrial-secondary transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <ChevronRight
            size={11}
            className={`transition-transform duration-200 ${open ? 'rotate-90' : ''}`}
          />
          Data Imports
          {activeJobs.length > 0 && (
            <span className="ml-1 inline-flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full bg-[var(--accent-subtle)] text-[10px] text-[var(--accent)]">
              {activeJobs.length}
            </span>
          )}
        </span>
      </button>

      {open && (
        <div className="space-y-2">
          {/* Source selector — small segmented chip */}
          <div className="flex items-center gap-1 text-[10.5px]">
            {(Object.keys(SOURCE_META) as ImportSource[]).map((src) => {
              const meta = SOURCE_META[src];
              const active = selectedSource === src;
              return (
                <button
                  key={src}
                  type="button"
                  onClick={() => setSelectedSource(src)}
                  className={`flex items-center gap-1 px-2 py-1 rounded-md border transition-colors ${
                    active
                      ? 'border-[var(--accent)] bg-[var(--accent-subtle)] text-[var(--accent)]'
                      : 'border-[var(--border-subtle)] text-industrial-muted hover:border-[var(--accent)]/30 hover:text-industrial'
                  }`}
                  title={meta.hint}
                >
                  {meta.icon}
                  <span className="font-medium">{meta.name}</span>
                </button>
              );
            })}
          </div>

          {/* Single dropzone */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`flex flex-col items-center justify-center gap-1.5 py-4 border border-dashed rounded-lg cursor-pointer transition-all ${
              isDragging
                ? 'border-[var(--accent)] bg-[var(--accent-subtle)] scale-[1.01]'
                : 'border-[var(--border-subtle)] hover:border-[var(--accent)]/30 hover:bg-[var(--bg-tertiary)]'
            }`}
          >
            <Upload size={16} className="text-industrial-muted" />
            <p className="text-[11px] text-industrial-muted">
              Drop {SOURCE_META[selectedSource].fileType} or{' '}
              <span className="text-[var(--accent)]">browse</span>
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept={SOURCE_META[selectedSource].accept}
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFile(file);
                e.target.value = '';
              }}
            />
          </div>

          {/* Compact status rows for active / finished jobs */}
          {activeJobs.length > 0 && (
            <div className="space-y-1">
              {activeJobs.map(([source, s]) => {
                const meta = SOURCE_META[source];
                return (
                  <div
                    key={source}
                    className="flex items-center gap-2 px-2 py-1.5 rounded-md bg-[var(--bg-tertiary)] border border-[var(--border-subtle)]"
                  >
                    {s.status === 'uploading' || s.status === 'parsing' ? (
                      <Loader2 size={12} className="text-[var(--accent)] animate-spin shrink-0" />
                    ) : s.status === 'ready' ? (
                      <CheckCircle2 size={12} className="text-emerald-400 shrink-0" />
                    ) : s.status === 'error' ? (
                      <AlertCircle size={12} className="text-red-400 shrink-0" />
                    ) : null}
                    <div className="flex-1 min-w-0">
                      <p className="text-[11px] font-medium text-industrial truncate">
                        {meta.name}
                        {s.fileName ? <span className="text-industrial-muted"> · {s.fileName}</span> : null}
                      </p>
                      <p
                        className={`text-[10.5px] truncate ${
                          s.status === 'ready'
                            ? 'text-emerald-400'
                            : s.status === 'error'
                              ? 'text-red-400'
                              : 'text-industrial-muted'
                        }`}
                      >
                        {s.status === 'uploading'
                          ? 'Uploading…'
                          : s.status === 'parsing'
                            ? 'Parsing data…'
                            : s.status === 'ready'
                              ? 'Ready'
                              : s.error || 'Failed'}
                      </p>
                    </div>
                    {(s.status === 'ready' || s.status === 'error') && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          reset(source);
                        }}
                        className="text-[10.5px] text-industrial-muted hover:text-industrial transition-colors"
                      >
                        {s.status === 'ready' ? 'Clear' : 'Retry'}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
