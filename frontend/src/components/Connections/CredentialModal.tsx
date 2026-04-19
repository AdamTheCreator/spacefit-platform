import { useCallback, useEffect } from 'react';
import { X, Upload, BarChart3, Building2, Users } from 'lucide-react';

const SOURCE_ICONS: Record<string, React.ReactNode> = {
  costar: <Building2 size={20} className="text-purple-400" />,
  placer: <Users size={20} className="text-green-400" />,
  siteusa: <BarChart3 size={20} className="text-blue-400" />,
};

const SOURCE_INFO: Record<string, { name: string; importType: string; description: string }> = {
  costar: { name: 'CoStar', importType: 'CSV', description: 'Upload CoStar lease comp or tenant roster exports' },
  placer: { name: 'Placer.ai', importType: 'PDF', description: 'Upload Placer property report PDFs' },
  siteusa: { name: 'SiteUSA', importType: 'CSV', description: 'Upload SiteUSA demographic exports' },
};

interface DataSourceModalProps {
  isOpen: boolean;
  onClose: () => void;
  sourceId: string | null;
}

export function CredentialModal({ isOpen, onClose, sourceId }: DataSourceModalProps) {
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape' && isOpen) onClose();
  }, [isOpen, onClose]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  if (!isOpen || !sourceId) return null;

  const info = SOURCE_INFO[sourceId] || { name: sourceId, importType: 'File', description: '' };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-[var(--bg-elevated)] border border-[var(--border-subtle)] rounded-2xl shadow-xl w-full max-w-md animate-scale-in">
        <div className="flex items-center justify-between p-5 border-b border-[var(--border-subtle)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[var(--bg-tertiary)] border border-[var(--border-subtle)] flex items-center justify-center">
              {SOURCE_ICONS[sourceId] || <BarChart3 size={20} className="text-industrial-muted" />}
            </div>
            <div>
              <h2 className="text-base font-semibold text-industrial">Import from {info.name}</h2>
              <p className="text-xs text-industrial-muted mt-0.5">{info.importType} upload</p>
            </div>
          </div>
          <button onClick={onClose} aria-label="Close" className="p-2 rounded-lg text-industrial-muted hover:text-industrial hover:bg-[var(--hover-overlay)] transition-colors">
            <X size={20} />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <p className="text-sm text-industrial-secondary">{info.description}</p>

          <div className="flex items-center justify-center p-8 border-2 border-dashed border-[var(--border-subtle)] rounded-lg bg-[var(--bg-tertiary)]">
            <div className="text-center">
              <Upload size={32} className="mx-auto text-industrial-muted mb-2" />
              <p className="text-sm font-medium text-industrial">Import coming in Phase 2</p>
              <p className="text-xs text-industrial-muted mt-1">CSV and PDF upload will be available soon</p>
            </div>
          </div>
        </div>

        <div className="flex gap-3 p-5 border-t border-[var(--border-subtle)]">
          <button onClick={onClose} className="flex-1 px-4 py-2.5 rounded-lg border border-[var(--border-default)] text-sm font-medium text-industrial hover:bg-[var(--hover-overlay)] transition-colors">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
