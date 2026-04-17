import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AppLayout } from '../components/Layout';
import {
  Key,
  CheckCircle,
  XCircle,
  RefreshCw,
  Clock,
  AlertTriangle,
  Loader2,
  Monitor,
  Plus,
  BarChart3,
  Building2,
  Users,
  ExternalLink,
} from 'lucide-react';
import { api } from '../lib/axios';
import type {
  Credential,
  SiteConfig,
  CredentialCreate,
  VerifyResult,
  SessionStatus,
  ConnectorStatus,
  ConnectorStatusItem,
} from '../types/credentials';
import { CredentialModal } from '../components/Connections/CredentialModal';
import { BrowserLoginModal } from '../components/Connections/BrowserLoginModal';
import { useConnectorStatus, connectorKeys } from '../hooks/useConnectorHealth';

// Map site IDs to Lucide icons
const SITE_ICONS: Record<string, React.ReactNode> = {
  siteusa: <BarChart3 size={24} className="text-blue-400" />,
  costar: <Building2 size={24} className="text-purple-400" />,
  placer: <Users size={24} className="text-green-400" />,
};

// Default site configs in case API fails
const DEFAULT_SITES: SiteConfig[] = [
  {
    id: 'placer',
    name: 'Placer.ai',
    description: 'Foot traffic, customer profiles, and tenant gap analysis',
    icon: 'users',
    url: 'https://analytics.placer.ai',
    data_types: ['foot_traffic', 'customer_profile', 'void_analysis'],
    typical_duration_seconds: 45,
    is_browser_based: true,
    requires_manual_login: true, // Has CAPTCHA
  },
  {
    id: 'siteusa',
    name: 'SiteUSA',
    description: 'Demographics, foot traffic, and tenant data',
    icon: 'chart-bar',
    url: 'https://regis.sitesusa.com',
    data_types: ['demographics', 'foot_traffic', 'tenant_data'],
    typical_duration_seconds: 45,
    is_browser_based: true,
    requires_manual_login: false,
  },
  {
    id: 'costar',
    name: 'CoStar',
    description: 'Commercial real estate analytics',
    icon: 'building',
    url: 'https://www.costar.com',
    data_types: ['property_info', 'tenant_data'],
    typical_duration_seconds: 60,
    is_browser_based: true,
    requires_manual_login: true, // CoStar blocks headless browsers
    coming_soon: false,
  },
];

function getStatusBadge(
  credential: Credential | undefined,
  isVerifying: boolean,
  requiresManualLogin?: boolean,
  connectorHealth?: ConnectorStatusItem,
): { icon: React.ReactNode; text: string; className: string; needsManualRefresh?: boolean } {
  if (!credential) {
    return {
      icon: <Key size={14} />,
      text: 'Not configured',
      className: 'text-industrial-muted',
    };
  }

  if (isVerifying) {
    return {
      icon: <Loader2 size={14} className="animate-spin" />,
      text: 'Checking...',
      className: 'text-[var(--accent)]',
    };
  }

  // Prefer connector health status when available
  const healthStatus = connectorHealth?.connector_status as ConnectorStatus | undefined;
  if (healthStatus) {
    switch (healthStatus) {
      case 'connected':
        return {
          icon: <CheckCircle size={14} />,
          text: 'Connected',
          className: 'text-[var(--color-success)]',
        };
      case 'stale':
      case 'unknown':
        return {
          icon: <Loader2 size={14} className="animate-spin" />,
          text: 'Connecting...',
          className: 'text-industrial-muted',
        };
      case 'needs_reauth':
        return {
          icon: <AlertTriangle size={14} />,
          text: 'Needs re-authentication',
          className: 'text-amber-500',
          needsManualRefresh: requiresManualLogin,
        };
      case 'degraded':
        return {
          icon: <AlertTriangle size={14} />,
          text: 'Intermittent issues',
          className: 'text-yellow-500',
        };
      case 'error':
        return {
          icon: <XCircle size={14} />,
          text: connectorHealth?.session_error_message || 'Connection error',
          className: 'text-[var(--color-error)]',
          needsManualRefresh: requiresManualLogin,
        };
      case 'disabled':
        return {
          icon: <XCircle size={14} />,
          text: 'Disabled',
          className: 'text-industrial-muted',
        };
    }
  }

  // Fallback to legacy session_status
  const status = credential.session_status as SessionStatus;

  switch (status) {
    case 'valid':
      return {
        icon: <CheckCircle size={14} />,
        text: 'Connected',
        className: 'text-[var(--color-success)]',
      };
    case 'expired':
      return {
        icon: <Clock size={14} />,
        text: requiresManualLogin ? 'Session expired - refresh needed' : 'Session expired',
        className: 'text-[var(--color-warning)]',
        needsManualRefresh: requiresManualLogin,
      };
    case 'requires_manual_login':
      return {
        icon: <ExternalLink size={14} />,
        text: 'Manual login required',
        className: 'text-[var(--color-warning)]',
        needsManualRefresh: true,
      };
    case 'error':
      return {
        icon: <XCircle size={14} />,
        text: credential.session_error_message || 'Connection error',
        className: 'text-[var(--color-error)]',
        needsManualRefresh: requiresManualLogin,
      };
    default:
      if (credential.is_verified) {
        return {
          icon: <CheckCircle size={14} />,
          text: 'Verified',
          className: 'text-[var(--color-success)]',
        };
      }
      return {
        icon: <AlertTriangle size={14} />,
        text: requiresManualLogin ? 'Login required' : 'Not verified',
        className: 'text-industrial-secondary',
        needsManualRefresh: requiresManualLogin,
      };
  }
}

interface ConnectionCardProps {
  site: SiteConfig;
  credential?: Credential;
  connectorHealth?: ConnectorStatusItem;
  onConnect: () => void;
  onVerify: () => void;
  onBrowserLogin: () => void;
  isVerifying: boolean;
}

function ConnectionCard({
  site,
  credential,
  connectorHealth,
  onConnect,
  onVerify,
  onBrowserLogin,
  isVerifying,
}: ConnectionCardProps) {
  const statusBadge = getStatusBadge(credential, isVerifying, site.requires_manual_login, connectorHealth);

  return (
    <div className="card-industrial">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-[var(--bg-tertiary)] border border-industrial-subtle flex items-center justify-center">
            {SITE_ICONS[site.id] || <BarChart3 size={24} className="text-industrial-muted" />}
          </div>
          <div>
            <h3 className="font-mono text-sm font-medium text-industrial flex items-center gap-2">
              {site.name}
              {site.is_browser_based && (
                <span className="font-mono text-[10px] uppercase tracking-wide bg-[var(--accent)]/10 text-[var(--accent)] px-2 py-0.5 border border-[var(--accent)]/30 flex items-center gap-1">
                  <Monitor size={10} />
                  Browser
                </span>
              )}
              {site.requires_manual_login && (
                <span className="font-mono text-[10px] uppercase tracking-wide bg-amber-500/10 text-amber-500 px-2 py-0.5 border border-amber-500/30 flex items-center gap-1">
                  <ExternalLink size={10} />
                  CAPTCHA
                </span>
              )}
              {site.coming_soon && (
                <span className="font-mono text-[10px] uppercase tracking-wide bg-[var(--bg-tertiary)] text-industrial-muted px-2 py-0.5 border border-industrial-subtle">
                  Coming soon
                </span>
              )}
            </h3>
            <p className="font-mono text-xs text-industrial-muted">{site.description}</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <span className={`flex items-center gap-2 font-mono text-xs ${statusBadge.className}`}>
            {statusBadge.icon}
            <span className="max-w-[150px] truncate">{statusBadge.text}</span>
          </span>

          <div className="flex gap-2">
            {/* Reconnect: shown when credentials exist but connection is unhealthy */}
            {credential && !site.coming_soon && statusBadge.needsManualRefresh && site.requires_manual_login && (
              <button
                onClick={onBrowserLogin}
                className="btn-industrial bg-amber-500 hover:bg-amber-600 text-white border-amber-600"
              >
                <RefreshCw size={14} />
                Reconnect
              </button>
            )}
            {credential && !site.coming_soon && !site.requires_manual_login &&
              connectorHealth?.connector_status &&
              ['needs_reauth', 'error'].includes(connectorHealth.connector_status) && (
              <button
                onClick={onVerify}
                disabled={isVerifying}
                className="btn-industrial bg-amber-500 hover:bg-amber-600 text-white border-amber-600"
              >
                {isVerifying ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                Reconnect
              </button>
            )}

            {/* Connect / Update credentials */}
            <button
              onClick={onConnect}
              disabled={site.coming_soon}
              className={credential
                ? 'btn-industrial-secondary disabled:opacity-50 disabled:cursor-not-allowed'
                : 'btn-industrial-primary disabled:opacity-50 disabled:cursor-not-allowed'
              }
            >
              {credential ? 'Update' : (<><Plus size={14} /> Connect</>)}
            </button>
          </div>
        </div>
      </div>

      {site.is_browser_based && !site.coming_soon && (
        <div className="mt-3 pt-3 border-t border-industrial-subtle">
          <p className="font-mono text-[10px] text-industrial-muted flex items-center gap-1 uppercase tracking-wide">
            <Clock size={12} />
            Browser-based connection: ~{site.typical_duration_seconds}s per query
            {site.requires_manual_login && ' • Requires manual CAPTCHA solve'}
          </p>
        </div>
      )}

      {credential && credential.total_uses > 0 && (
        <div className="mt-2 font-mono text-[10px] text-industrial-muted">
          Used {credential.total_uses} time{credential.total_uses !== 1 ? 's' : ''}
          {credential.last_used_at && (
            <> • Last used {new Date(credential.last_used_at).toLocaleDateString()}</>
          )}
        </div>
      )}
    </div>
  );
}

export function ConnectionsPage() {
  const queryClient = useQueryClient();
  const [verifyingIds, setVerifyingIds] = useState<Set<string>>(new Set());
  const [modalOpen, setModalOpen] = useState(false);
  const [savePhase, setSavePhase] = useState<'idle' | 'saving' | 'verifying'>('idle');
  const [browserLoginOpen, setBrowserLoginOpen] = useState(false);
  const [selectedSite, setSelectedSite] = useState<SiteConfig | null>(null);
  const [existingCredential, setExistingCredential] = useState<Credential | null>(null);

  // Connector health
  const { data: healthStatuses } = useConnectorStatus();

  // Fetch available sites from API
  const { data: sites = DEFAULT_SITES } = useQuery({
    queryKey: ['credential-sites'],
    queryFn: async () => {
      const res = await api.get('/credentials/sites');
      return res.data as SiteConfig[];
    },
    staleTime: 60000,
  });

  // Fetch user's credentials
  const { data: credentials = [] } = useQuery({
    queryKey: ['credentials'],
    queryFn: async () => {
      const res = await api.get('/credentials');
      return res.data as Credential[];
    },
  });

  // Create credential mutation
  const createMutation = useMutation({
    mutationFn: async (data: CredentialCreate) => {
      const res = await api.post('/credentials', data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credentials'] });
    },
  });

  // Update credential mutation
  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<CredentialCreate> }) => {
      const res = await api.put(`/credentials/${id}`, data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credentials'] });
    },
  });

  // Delete credential mutation
  const deleteMutation = useMutation({
    mutationFn: async (credentialId: string) => {
      await api.delete(`/credentials/${credentialId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credentials'] });
      setModalOpen(false);
    },
  });

  // Verify credential mutation (supports parallel verifications)
  const verifyMutation = useMutation({
    mutationFn: async (credentialId: string) => {
      const res = await api.post(`/credentials/${credentialId}/verify`);
      return res.data as VerifyResult;
    },
    onMutate: (id) => setVerifyingIds((prev) => new Set(prev).add(id)),
    onSettled: (_data, _error, id) => {
      setVerifyingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      queryClient.invalidateQueries({ queryKey: ['credentials'] });
    },
  });

  const getCredentialForSite = (siteId: string) => {
    return credentials.find((c) => c.site_name.toLowerCase() === siteId.toLowerCase());
  };

  const handleConnect = (site: SiteConfig) => {
    const existing = getCredentialForSite(site.id);
    setSelectedSite(site);
    setExistingCredential(existing || null);
    setModalOpen(true);
  };

  const handleBrowserLogin = (site: SiteConfig) => {
    const existing = getCredentialForSite(site.id);
    setSelectedSite(site);
    setExistingCredential(existing || null);
    setBrowserLoginOpen(true);
  };

  const handleBrowserLoginSuccess = () => {
    queryClient.invalidateQueries({ queryKey: ['credentials'] });
    queryClient.invalidateQueries({ queryKey: connectorKeys.status() });
    setBrowserLoginOpen(false);
  };

  const getHealthForSite = (siteId: string): ConnectorStatusItem | undefined => {
    return healthStatuses?.find((h) => h.site_name === siteId);
  };

  const handleSave = async (username: string, password: string) => {
    if (!selectedSite) return;

    try {
      setSavePhase('saving');

      let credentialId: string;
      if (existingCredential) {
        const result = await updateMutation.mutateAsync({
          id: existingCredential.id,
          data: { username, password },
        });
        credentialId = result.id ?? existingCredential.id;
      } else {
        const result = await createMutation.mutateAsync({
          site_name: selectedSite.id,
          site_url: selectedSite.url,
          username,
          password,
        });
        credentialId = result.id;
      }

      // Auto-verify for non-CAPTCHA sites (best-effort — don't block save)
      if (!selectedSite.requires_manual_login) {
        setSavePhase('verifying');
        try {
          await api.post(`/credentials/${credentialId}/verify`);
        } catch {
          // Verify can fail (e.g. browser not available on server) —
          // credential is already saved, so just continue.
        }
        queryClient.invalidateQueries({ queryKey: ['credentials'] });
        queryClient.invalidateQueries({ queryKey: connectorKeys.status() });
      }

      setModalOpen(false);
    } finally {
      setSavePhase('idle');
    }
  };

  const handleDelete = async () => {
    if (!existingCredential) return;
    await deleteMutation.mutateAsync(existingCredential.id);
  };

  return (
    <AppLayout>
      <div className="p-6 max-w-4xl mx-auto bg-industrial min-h-full">
        <h1 className="font-mono text-lg font-bold tracking-tight text-industrial mb-2">Connections</h1>
        <p className="font-mono text-xs text-industrial-muted mb-6">
          Connect your data sources to enable real-time property analysis.
        </p>

        <div className="space-y-4">
          {sites.map((site) => {
            const credential = getCredentialForSite(site.id);
            const health = getHealthForSite(site.id);
            return (
              <ConnectionCard
                key={site.id}
                site={site}
                credential={credential}
                connectorHealth={health}
                onConnect={() => handleConnect(site)}
                onVerify={() => credential && verifyMutation.mutate(credential.id)}
                onBrowserLogin={() => handleBrowserLogin(site)}
                isVerifying={credential ? verifyingIds.has(credential.id) : false}
              />
            );
          })}
        </div>

        <div className="mt-8 p-4 bg-[var(--accent)]/5 border border-[var(--accent)]/30">
          <h3 className="font-mono text-xs font-semibold uppercase tracking-wide text-[var(--accent)] mb-2 flex items-center gap-2">
            <Monitor size={16} />
            About Browser-Based Connections
          </h3>
          <p className="font-mono text-xs text-industrial-secondary">
            Some data sources require browser automation to access your existing
            subscriptions. These connections are slower than API-based sources (typically
            30-90 seconds per query) but provide access to premium data. Your credentials
            are encrypted using AES-256 and stored securely.
          </p>
        </div>

        {verifyMutation.isError && (
          <div className="mt-4 p-4 bg-[var(--color-error)]/10 border border-[var(--color-error)]/30">
            <p className="font-mono text-xs text-[var(--color-error)]">
              Verification failed. Please check your credentials and try again.
            </p>
          </div>
        )}
      </div>

      <CredentialModal
        isOpen={modalOpen}
        onClose={() => { if (savePhase === 'idle') setModalOpen(false); }}
        site={selectedSite}
        existingCredential={existingCredential}
        onSave={handleSave}
        onDelete={handleDelete}
        isLoading={savePhase !== 'idle' || deleteMutation.isPending}
        loadingText={savePhase === 'verifying' ? 'Verifying connection...' : 'Saving...'}
        error={
          createMutation.error?.message ||
          updateMutation.error?.message ||
          deleteMutation.error?.message ||
          null
        }
      />

      <BrowserLoginModal
        isOpen={browserLoginOpen}
        onClose={() => setBrowserLoginOpen(false)}
        site={selectedSite}
        existingCredential={existingCredential}
        onSuccess={handleBrowserLoginSuccess}
      />
    </AppLayout>
  );
}
