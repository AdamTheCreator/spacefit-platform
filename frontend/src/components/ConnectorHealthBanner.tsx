import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, X, ArrowRight } from 'lucide-react';
import { useConnectorIssues } from '../hooks/useConnectorHealth';

/**
 * Global warning banner shown when one or more connectors need attention.
 * Rendered between the header and <main> in AppLayout.
 */
export function ConnectorHealthBanner() {
  const { issues, count, isLoading } = useConnectorIssues();
  const [dismissed, setDismissed] = useState(false);

  if (isLoading || count === 0 || dismissed) return null;

  const message =
    count === 1
      ? `${issues[0].site_display_name} needs re-authentication`
      : `${count} connectors need attention`;

  return (
    <div className="flex items-center gap-3 px-4 py-2.5 bg-amber-500/10 border-b border-amber-500/20">
      <AlertTriangle size={16} className="text-amber-500 flex-shrink-0" />
      <span className="flex-1 text-sm text-industrial-secondary">
        {message}
      </span>
      <Link
        to="/connections"
        className="flex items-center gap-1.5 text-sm font-medium text-amber-500 hover:text-amber-400 transition-colors"
      >
        Fix now
        <ArrowRight size={14} />
      </Link>
      <button
        onClick={() => setDismissed(true)}
        className="p-1 rounded text-industrial-muted hover:text-industrial hover:bg-[var(--hover-overlay)] transition-colors"
        aria-label="Dismiss banner"
      >
        <X size={14} />
      </button>
    </div>
  );
}
