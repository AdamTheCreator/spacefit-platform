import { useState } from 'react';
import { FileText, Download, Share2, Check, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import api from '../../lib/axios';

interface ExportBarProps {
  sessionId: string;
}

export function ExportBar({ sessionId }: ExportBarProps) {
  const [loading, setLoading] = useState<'pdf' | 'csv' | 'share' | null>(null);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const exportButtonClassName =
    'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--border-default)] hover:bg-[var(--bg-secondary)] text-xs font-medium text-industrial-secondary transition-colors';

  const handleExportPDF = async () => {
    setLoading('pdf');
    try {
      const response = await api.post(
        '/reports/generate/pdf',
        { session_id: sessionId, report_type: 'comprehensive' },
        { responseType: 'blob' },
      );
      const url = URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `report-${sessionId.slice(0, 8)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('PDF downloaded');
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail || 'Failed to generate PDF');
    } finally {
      setLoading(null);
    }
  };

  const handleExportCSV = async () => {
    setLoading('csv');
    try {
      const response = await api.get(
        `/reports/sessions/${sessionId}/csv`,
        { responseType: 'blob' },
      );
      const url = URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `data-${sessionId.slice(0, 8)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('CSV downloaded');
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail || 'Failed to export CSV');
    } finally {
      setLoading(null);
    }
  };

  const handleShare = async () => {
    setLoading('share');
    try {
      const { data } = await api.post('/reports/share', {
        session_id: sessionId,
        report_type: 'comprehensive',
      });
      const fullUrl = `${window.location.origin}${data.share_url}`;
      await navigator.clipboard.writeText(fullUrl);
      setShareUrl(fullUrl);
      toast.success('Share link copied to clipboard');
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail || 'Failed to create share link');
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="flex items-center gap-2 pl-11 sm:pl-13 animate-fade-in">
      <span className="text-xs text-industrial-muted mr-1">Export:</span>

      <button
        onClick={handleExportPDF}
        disabled={loading !== null}
        className={exportButtonClassName}
      >
        {loading === 'pdf' ? <Loader2 size={12} className="animate-spin" /> : <FileText size={12} />}
        PDF
      </button>

      <button
        onClick={handleExportCSV}
        disabled={loading !== null}
        className={exportButtonClassName}
      >
        {loading === 'csv' ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
        CSV
      </button>

      <button
        onClick={handleShare}
        disabled={loading !== null}
        className={exportButtonClassName}
      >
        {loading === 'share' ? (
          <Loader2 size={12} className="animate-spin" />
        ) : shareUrl ? (
          <Check size={12} />
        ) : (
          <Share2 size={12} />
        )}
        {shareUrl ? 'Copied' : 'Share'}
      </button>
    </div>
  );
}
