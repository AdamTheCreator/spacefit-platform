import { useState, useEffect, useCallback } from 'react';
import { X, Sparkles, MapPin } from 'lucide-react';
import { Button } from '../ui/Button';

interface StartAnalysisModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (options: AnalysisOptions) => void;
  isLoading: boolean;
  propertyName?: string | null;
  propertyAddress?: string | null;
  tenantCount?: number;
  availableSpaceCount?: number;
  documentType?: string;
}

export interface AnalysisOptions {
  analysisType: string;
  tradeAreaMiles: number;
  notes: string;
}

const ANALYSIS_TYPES = [
  {
    value: 'void_analysis',
    label: 'Find Tenant Gaps',
    description: 'Identify missing tenant categories and recommend specific tenants for available spaces.',
  },
  {
    value: 'competitive_analysis',
    label: 'Competitive Analysis',
    description: 'Analyze the competitive landscape around the property.',
  },
  {
    value: 'demographic_profile',
    label: 'Demographic Profile',
    description: 'Deep dive into trade area demographics and customer segmentation.',
  },
];

export function StartAnalysisModal({
  isOpen,
  onClose,
  onConfirm,
  isLoading,
  propertyName,
  propertyAddress,
  tenantCount,
  availableSpaceCount,
  documentType,
}: StartAnalysisModalProps) {
  const [analysisType, setAnalysisType] = useState('void_analysis');
  const [tradeAreaMiles, setTradeAreaMiles] = useState(3);
  const [notes, setNotes] = useState('');

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setAnalysisType('void_analysis');
      setTradeAreaMiles(3);
      setNotes('');
    }
  }, [isOpen]);

  // Handle Escape key
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !isLoading) {
        onClose();
      }
    },
    [isOpen, isLoading, onClose],
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onConfirm({
      analysisType,
      tradeAreaMiles,
      notes,
    });
  };

  const selectedType = ANALYSIS_TYPES.find((t) => t.value === analysisType);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={!isLoading ? onClose : undefined}
      />

      {/* Modal */}
      <div className="relative bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-subtle)]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[var(--accent-subtle)] flex items-center justify-center">
              <Sparkles size={18} className="text-[var(--accent)]" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-industrial">Start Analysis</h2>
              <p className="text-xs text-industrial-muted">Configure and launch AI analysis</p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isLoading}
            className="p-1.5 rounded-lg hover:bg-[var(--bg-tertiary)] text-industrial-muted hover:text-industrial transition-colors disabled:opacity-50"
          >
            <X size={18} />
          </button>
        </div>

        {/* Property Summary */}
        <div className="px-6 py-4 bg-[var(--bg-secondary)] border-b border-[var(--border-subtle)]">
          <div className="flex items-start gap-3">
            <MapPin size={16} className="text-industrial-muted mt-0.5 flex-shrink-0" />
            <div className="min-w-0">
              {propertyName && (
                <p className="text-sm font-medium text-industrial truncate">{propertyName}</p>
              )}
              {propertyAddress && (
                <p className="text-xs text-industrial-muted truncate">{propertyAddress}</p>
              )}
              <div className="flex items-center gap-3 mt-2">
                {tenantCount != null && tenantCount > 0 && (
                  <span className="px-2 py-0.5 bg-[var(--bg-primary)] border border-[var(--border-subtle)] rounded-full text-[10px] font-medium text-industrial-secondary">
                    {tenantCount} tenant{tenantCount !== 1 ? 's' : ''}
                  </span>
                )}
                {availableSpaceCount != null && availableSpaceCount > 0 && (
                  <span className="px-2 py-0.5 bg-[var(--bg-success)] text-[var(--color-success)] rounded-full text-[10px] font-medium">
                    {availableSpaceCount} space{availableSpaceCount !== 1 ? 's' : ''} available
                  </span>
                )}
                {documentType && (
                  <span className="px-2 py-0.5 bg-[var(--bg-primary)] border border-[var(--border-subtle)] rounded-full text-[10px] font-medium text-industrial-muted">
                    {documentType.replace('_', ' ')}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <div className="px-6 py-5 space-y-5">
            {/* Analysis Type */}
            <div>
              <label className="block text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-2">
                Analysis Type
              </label>
              <div className="space-y-2">
                {ANALYSIS_TYPES.map((type) => (
                  <label
                    key={type.value}
                    className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all ${
                      analysisType === type.value
                        ? 'border-[var(--accent)] bg-[var(--accent-subtle)]'
                        : 'border-[var(--border-subtle)] hover:border-[var(--border-default)] bg-[var(--bg-secondary)]'
                    }`}
                  >
                    <input
                      type="radio"
                      name="analysisType"
                      value={type.value}
                      checked={analysisType === type.value}
                      onChange={(e) => setAnalysisType(e.target.value)}
                      className="mt-0.5 accent-[var(--accent)]"
                    />
                    <div>
                      <p className="text-sm font-medium text-industrial">{type.label}</p>
                      <p className="text-xs text-industrial-muted mt-0.5">{type.description}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* Trade Area */}
            <div>
              <label className="block text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-2">
                Trade Area Radius
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min={1}
                  max={10}
                  step={0.5}
                  value={tradeAreaMiles}
                  onChange={(e) => setTradeAreaMiles(Number(e.target.value))}
                  className="flex-1 accent-[var(--accent)]"
                />
                <span className="text-sm font-medium text-industrial tabular-nums w-16 text-right">
                  {tradeAreaMiles} mi
                </span>
              </div>
            </div>

            {/* Custom Instructions */}
            <div>
              <label className="block text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-2">
                Custom Instructions <span className="font-normal">(optional)</span>
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="e.g. Focus on QSR and fast-casual, national credit tenants only..."
                rows={2}
                className="w-full px-3 py-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-subtle)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)] resize-none"
              />
            </div>
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-[var(--border-subtle)] flex items-center justify-between">
            <p className="text-xs text-industrial-muted">
              {selectedType?.label} will begin immediately
            </p>
            <div className="flex items-center gap-3">
              <Button
                type="button"
                variant="ghost"
                onClick={onClose}
                disabled={isLoading}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                loading={isLoading}
                iconLeft={!isLoading ? <Sparkles size={14} /> : undefined}
              >
                {isLoading ? 'Creating…' : 'Start Analysis'}
              </Button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
