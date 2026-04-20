import { useState, useRef, useCallback } from 'react';
import {
  Upload,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Building2,
  Users,
  BarChart3,
} from 'lucide-react';
import api from '../../lib/axios';

const SOURCE_CONFIG: Record<
  string,
  {
    name: string;
    icon: React.ReactNode;
    accept: string;
    fileType: string;
    description: string;
  }
> = {
  costar: {
    name: 'CoStar',
    icon: <Building2 size={18} className="text-purple-400" />,
    accept: '.csv,.tsv,.txt',
    fileType: 'CSV',
    description: 'Lease comps, tenant rosters, property details',
  },
  placer: {
    name: 'Placer.ai',
    icon: <Users size={18} className="text-green-400" />,
    accept: '.pdf',
    fileType: 'PDF',
    description: 'Property report with foot traffic and demographics',
  },
  siteusa: {
    name: 'SiteUSA',
    icon: <BarChart3 size={18} className="text-blue-400" />,
    accept: '.csv,.tsv,.txt',
    fileType: 'CSV',
    description: 'Vehicle traffic counts and demographics',
  },
};

interface ImportUploadCardProps {
  source: string;
  projectId?: string;
  onUploadComplete?: () => void;
}

type UploadStatus = 'idle' | 'uploading' | 'parsing' | 'ready' | 'error';

export function ImportUploadCard({
  source,
  projectId,
  onUploadComplete,
}: ImportUploadCardProps) {
  const [status, setStatus] = useState<UploadStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const config = SOURCE_CONFIG[source];
  if (!config) return null;

  const handleUpload = useCallback(
    async (file: File) => {
      setFileName(file.name);
      setStatus('uploading');
      setError(null);

      const formData = new FormData();
      formData.append('file', file);

      const endpoint = projectId
        ? `/projects/${projectId}/imports/${source}`
        : `/imports/${source}`;

      try {
        const res = await api.post(endpoint, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        const jobId = res.data.id;
        setStatus('parsing');

        // Poll until ready or error
        const poll = async () => {
          for (let i = 0; i < 60; i++) {
            await new Promise((r) => setTimeout(r, 2000));
            const detail = await api.get(`/imports/${jobId}`);
            if (detail.data.status === 'ready') {
              setStatus('ready');
              onUploadComplete?.();
              return;
            }
            if (detail.data.status === 'error') {
              setStatus('error');
              setError(detail.data.error_message || 'Parse failed');
              return;
            }
          }
          setStatus('error');
          setError('Timed out waiting for parse');
        };
        poll();
      } catch (err: unknown) {
        setStatus('error');
        setError(err instanceof Error ? err.message : 'Upload failed');
      }
    },
    [source, projectId, onUploadComplete],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleUpload(file);
    },
    [handleUpload],
  );

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleUpload(file);
      e.target.value = '';
    },
    [handleUpload],
  );

  const reset = () => {
    setStatus('idle');
    setError(null);
    setFileName(null);
  };

  return (
    <div className="card-industrial">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-8 h-8 bg-[var(--bg-tertiary)] border border-industrial-subtle flex items-center justify-center rounded-lg">
          {config.icon}
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="font-mono text-xs font-medium text-industrial flex items-center gap-2">
            {config.name}
            <span className="font-mono text-[10px] uppercase tracking-wide bg-[var(--bg-tertiary)] text-industrial-muted px-1.5 py-0.5 border border-industrial-subtle rounded">
              {config.fileType}
            </span>
          </h4>
          <p className="font-mono text-[11px] text-industrial-muted truncate">
            {config.description}
          </p>
        </div>
      </div>

      {status === 'idle' && (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`flex flex-col items-center justify-center gap-2 py-5 border-2 border-dashed rounded-lg cursor-pointer transition-all ${
            isDragging
              ? 'border-[var(--accent)] bg-[var(--accent-subtle)] scale-[1.01]'
              : 'border-[var(--border-subtle)] hover:border-[var(--accent)]/30 hover:bg-[var(--bg-tertiary)]'
          }`}
        >
          <Upload size={20} className="text-industrial-muted" />
          <p className="text-xs text-industrial-muted">
            Drop {config.fileType} or{' '}
            <span className="text-[var(--accent)]">browse</span>
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept={config.accept}
            className="hidden"
            onChange={handleFileChange}
          />
        </div>
      )}

      {(status === 'uploading' || status === 'parsing') && (
        <div className="flex items-center gap-3 py-3 px-4 rounded-lg bg-[var(--accent-subtle)] border border-[var(--accent)]/20">
          <Loader2 size={16} className="text-[var(--accent)] animate-spin" />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-industrial truncate">
              {fileName}
            </p>
            <p className="text-[11px] text-industrial-muted">
              {status === 'uploading' ? 'Uploading...' : 'Parsing data...'}
            </p>
          </div>
        </div>
      )}

      {status === 'ready' && (
        <div className="flex items-center gap-3 py-3 px-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
          <CheckCircle2 size={16} className="text-emerald-400" />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-industrial truncate">
              {fileName}
            </p>
            <p className="text-[11px] text-emerald-400">Import ready</p>
          </div>
          <button
            onClick={reset}
            className="text-[11px] text-industrial-muted hover:text-industrial transition-colors"
          >
            Upload another
          </button>
        </div>
      )}

      {status === 'error' && (
        <div className="flex items-center gap-3 py-3 px-4 rounded-lg bg-red-500/10 border border-red-500/20">
          <AlertCircle size={16} className="text-red-400" />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-industrial truncate">
              {fileName}
            </p>
            <p className="text-[11px] text-red-400 truncate">
              {error || 'Failed'}
            </p>
          </div>
          <button
            onClick={reset}
            className="text-[11px] text-industrial-muted hover:text-industrial transition-colors"
          >
            Retry
          </button>
        </div>
      )}
    </div>
  );
}
