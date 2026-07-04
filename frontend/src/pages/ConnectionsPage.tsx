import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { AppLayout } from '../components/Layout';
import { Upload, Mail, CheckCircle2 } from 'lucide-react';
import { ImportUploadCard } from '../components/Imports/ImportUploadCard';
import {
  useGmailStatus,
  useConnectGmail,
  useDisconnectGmail,
} from '../hooks/useGmailConnection';

const SOURCES = ['costar', 'placer', 'siteusa'] as const;

function GmailConnectionCard() {
  const { data: status, isLoading } = useGmailStatus();
  const connect = useConnectGmail();
  const disconnect = useDisconnectGmail();

  const handleConnect = () => {
    connect.mutate(undefined, {
      onError: () => {
        toast.error(
          'Gmail integration is not available. Ask your admin to configure it, or use SMTP.'
        );
      },
    });
  };

  const handleDisconnect = () => {
    disconnect.mutate(undefined, {
      onSuccess: () => toast.success('Gmail disconnected.'),
      onError: () => toast.error('Could not disconnect Gmail. Try again.'),
    });
  };

  return (
    <div className="p-4 card-industrial">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <Mail size={18} className="mt-0.5 text-[var(--accent)]" />
          <div>
            <h3 className="font-mono text-sm font-semibold text-industrial">
              Gmail
            </h3>
            <p className="font-mono text-xs text-industrial-muted mt-1">
              Connect Gmail to send outreach campaigns from your own inbox and
              sync replies. Without it, campaigns can't be delivered.
            </p>
            {status?.connected && status.email && (
              <p className="font-mono text-xs text-industrial-secondary mt-2 flex items-center gap-1.5">
                <CheckCircle2 size={14} className="text-[var(--accent)]" />
                Connected as {status.email}
              </p>
            )}
          </div>
        </div>
        <div className="shrink-0">
          {status?.connected ? (
            <button
              className="btn-industrial-secondary text-xs px-3 py-2 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={handleDisconnect}
              disabled={disconnect.isPending}
            >
              {disconnect.isPending ? 'Disconnecting…' : 'Disconnect'}
            </button>
          ) : (
            <button
              className="btn-industrial-primary text-xs px-3 py-2 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={handleConnect}
              disabled={isLoading || connect.isPending}
            >
              {connect.isPending ? 'Redirecting…' : 'Connect Gmail'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function ConnectionsPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    const gmail = searchParams.get('gmail');
    if (!gmail) return;
    if (gmail === 'connected') {
      toast.success('Gmail connected. You can now send outreach campaigns.');
    } else if (gmail === 'error') {
      const reason = searchParams.get('reason');
      const message =
        reason === 'profile'
          ? 'Gmail connected, but we could not read your address. Make sure the Gmail API is enabled for the project, then try again.'
          : reason === 'token_exchange'
            ? 'Gmail authorization could not be completed (token exchange failed). Please try again.'
            : 'Gmail connection failed. Please try again.';
      toast.error(message);
    }
    const next = new URLSearchParams(searchParams);
    next.delete('gmail');
    next.delete('reason');
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  return (
    <AppLayout>
      <div className="p-6 max-w-4xl mx-auto bg-industrial min-h-full">
        <h1 className="font-mono text-lg font-bold tracking-tight text-industrial mb-2">
          Connections
        </h1>
        <p className="font-mono text-xs text-industrial-muted mb-6">
          Connect email for outreach and upload data that you want to reuse
          across multiple projects. For deal-specific imports, upload them
          directly inside the project instead.
        </p>

        <h2 className="font-mono text-xs font-semibold uppercase tracking-wide text-industrial-muted mb-3">
          Email
        </h2>
        <div className="mb-8">
          <GmailConnectionCard />
        </div>

        <h2 className="font-mono text-xs font-semibold uppercase tracking-wide text-industrial-muted mb-3">
          Data Library
        </h2>
        <div className="space-y-4">
          {SOURCES.map((source) => (
            <ImportUploadCard key={source} source={source} />
          ))}
        </div>

        <div className="mt-8 p-4 bg-[var(--accent)]/5 border border-[var(--accent)]/30">
          <h3 className="font-mono text-xs font-semibold uppercase tracking-wide text-[var(--accent)] mb-2 flex items-center gap-2">
            <Upload size={16} />
            How Imports Work
          </h3>
          <p className="font-mono text-xs text-industrial-secondary">
            Export data from your CoStar, Placer.ai, or SiteUSA account, then
            upload the file here. Space Goose parses and structures the data so the
            AI can use it during analysis. No passwords or login credentials are
            stored.
          </p>
        </div>
      </div>
    </AppLayout>
  );
}
