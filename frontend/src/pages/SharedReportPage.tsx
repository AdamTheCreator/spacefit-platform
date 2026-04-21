import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Sparkles, AlertCircle } from 'lucide-react';
import axios from 'axios';

const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/api\/v1\/?$/, '');

interface SharedReport {
  title: string | null;
  report_type: string;
  content: string;
  created_at: string;
  expires_at: string;
}

export function SharedReportPage() {
  const { shareToken } = useParams<{ shareToken: string }>();
  const [report, setReport] = useState<SharedReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!shareToken) return;

    axios
      .get(`${API_URL}/api/v1/reports/shared/${shareToken}`)
      .then(({ data }) => setReport(data))
      .catch((err) => {
        const status = err.response?.status;
        if (status === 410) {
          setError('This report has expired.');
        } else if (status === 404) {
          setError('Report not found.');
        } else {
          setError('Failed to load report.');
        }
      })
      .finally(() => setLoading(false));
  }, [shareToken]);

  if (loading) {
    return (
      <div className="h-screen w-screen bg-[var(--bg-primary)] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-[var(--accent)] text-white flex items-center justify-center shadow-lg shadow-[var(--accent)]/20 animate-pulse-slow">
            <Sparkles size={24} />
          </div>
          <p className="text-xs font-bold tracking-widest uppercase text-industrial-muted">
            Loading report
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-screen w-screen bg-[var(--bg-primary)] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-center max-w-sm">
          <AlertCircle size={40} className="text-[var(--color-error)]" />
          <h2 className="text-xl font-semibold text-industrial">{error}</h2>
          <p className="text-sm text-industrial-muted">
            The link may have expired or been removed.
          </p>
        </div>
      </div>
    );
  }

  if (!report) return null;

  // Simple markdown-to-HTML for headings, bold, bullets
  const renderContent = (md: string) => {
    return md.split('\n').map((line, i) => {
      const trimmed = line.trim();
      if (!trimmed) return <div key={i} className="h-3" />;
      if (trimmed === '---') return <hr key={i} className="border-[var(--border-default)] my-4" />;
      if (trimmed.startsWith('## '))
        return <h2 key={i} className="text-lg font-semibold text-industrial mt-6 mb-2">{trimmed.slice(3)}</h2>;
      if (trimmed.startsWith('### '))
        return <h3 key={i} className="text-base font-semibold text-industrial mt-4 mb-1">{trimmed.slice(4)}</h3>;
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        const text = trimmed.slice(2).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
        return <p key={i} className="text-sm text-industrial-secondary pl-4 py-0.5" dangerouslySetInnerHTML={{ __html: `&bull; ${text}` }} />;
      }
      const text = trimmed.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
      return <p key={i} className="text-sm text-industrial-secondary py-0.5" dangerouslySetInnerHTML={{ __html: text }} />;
    });
  };

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      {/* Header */}
      <header className="border-b border-[var(--border-subtle)] bg-[var(--bg-secondary)]">
        <div className="max-w-[840px] mx-auto px-6 py-4 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent)] text-white flex items-center justify-center">
            <Sparkles size={16} />
          </div>
          <span className="text-sm font-semibold text-industrial">Perigee</span>
          <span className="text-xs text-industrial-muted ml-auto">
            Shared report
          </span>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-[840px] mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold text-industrial mb-1">
          {report.title || 'Analysis Report'}
        </h1>
        <p className="text-xs text-industrial-muted mb-6">
          Generated {new Date(report.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
        </p>

        <div className="border-t border-[var(--border-default)] pt-6">
          {renderContent(report.content)}
        </div>
      </main>
    </div>
  );
}
