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
} from 'lucide-react';
import { api } from '../lib/axios';
import type {
  Credential,
  SiteConfig,
  CredentialCreate,
  VerifyResult,
  SessionStatus,
} from '../types/credentials';
import { CredentialModal } from '../components/Connections/CredentialModal';

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
    description: 'Foot traffic, customer profiles, and void analysis',
    icon: 'users',
    url: 'https://analytics.placer.ai',
    data_types: ['foot_traffic', 'customer_profile', 'void_analysis'],
    typical_duration_seconds: 45,
    is_browser_based: true,
  },
  {
    id: 'siteusa',
    name: 'SiteUSA',
    description: 'Demographics, foot traffic, and tenant data',
    icon: 'chart-bar',
    url: 'https://www.siteusa.com',
    data_types: ['demographics', 'foot_traffic', 'tenant_data'],
    typical_duration_seconds: 45,
    is_browser_based: true,
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
    coming_soon: true,
  },
];

function getStatusBadge(
  credential: Credential | undefined,
  isVerifying: boolean
): { icon: React.ReactNode; text: string; className: string } {
  if (!credential) {
    return {
      icon: <Key size={16} />,
      text: 'Not configured',
      className: 'text-gray-500',
    };
  }

  if (isVerifying) {
    return {
      icon: <Loader2 size={16} className="animate-spin" />,
      text: 'Verifying...',
      className: 'text-blue-400',
    };
  }

  const status = credential.session_status as SessionStatus;

  switch (status) {
    case 'valid':
      return {
        icon: <CheckCircle size={16} />,
        text: 'Connected',
        className: 'text-green-400',
      };
    case 'expired':
      return {
        icon: <Clock size={16} />,
        text: 'Session expired',
        className: 'text-yellow-400',
      };
    case 'error':
      return {
        icon: <XCircle size={16} />,
        text: credential.session_error_message || 'Connection error',
        className: 'text-red-400',
      };
    default:
      if (credential.is_verified) {
        return {
          icon: <CheckCircle size={16} />,
          text: 'Verified',
          className: 'text-green-400',
        };
      }
      return {
        icon: <AlertTriangle size={16} />,
        text: 'Not verified',
        className: 'text-gray-400',
      };
  }
}

interface ConnectionCardProps {
  site: SiteConfig;
  credential?: Credential;
  onConnect: () => void;
  onVerify: () => void;
  isVerifying: boolean;
}

function ConnectionCard({
  site,
  credential,
  onConnect,
  onVerify,
  isVerifying,
}: ConnectionCardProps) {
  const statusBadge = getStatusBadge(credential, isVerifying);

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-gray-700 rounded-lg flex items-center justify-center">
            {SITE_ICONS[site.id] || <BarChart3 size={24} className="text-gray-400" />}
          </div>
          <div>
            <h3 className="text-white font-medium flex items-center gap-2">
              {site.name}
              {site.is_browser_based && (
                <span className="text-xs bg-purple-900/50 text-purple-300 px-2 py-0.5 rounded flex items-center gap-1">
                  <Monitor size={10} />
                  Browser
                </span>
              )}
              {site.coming_soon && (
                <span className="text-xs bg-gray-700 text-gray-400 px-2 py-0.5 rounded">
                  Coming soon
                </span>
              )}
            </h3>
            <p className="text-gray-400 text-sm">{site.description}</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <span className={`flex items-center gap-2 text-sm ${statusBadge.className}`}>
            {statusBadge.icon}
            <span className="max-w-[150px] truncate">{statusBadge.text}</span>
          </span>

          <div className="flex gap-2">
            {credential && !site.coming_soon && (
              <button
                onClick={onVerify}
                disabled={isVerifying}
                className="p-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors disabled:opacity-50"
                title="Re-verify connection"
              >
                <RefreshCw size={16} className={isVerifying ? 'animate-spin' : ''} />
              </button>
            )}

            <button
              onClick={onConnect}
              disabled={site.coming_soon}
              className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {credential ? 'Update' : 'Connect'}
              {!credential && <Plus size={14} />}
            </button>
          </div>
        </div>
      </div>

      {site.is_browser_based && !site.coming_soon && (
        <div className="mt-3 pt-3 border-t border-gray-700">
          <p className="text-xs text-gray-500 flex items-center gap-1">
            <Clock size={12} />
            Browser-based connection: ~{site.typical_duration_seconds}s per query
          </p>
        </div>
      )}

      {credential && credential.total_uses > 0 && (
        <div className="mt-2 text-xs text-gray-500">
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
  const [verifyingId, setVerifyingId] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedSite, setSelectedSite] = useState<SiteConfig | null>(null);
  const [existingCredential, setExistingCredential] = useState<Credential | null>(null);

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
      setModalOpen(false);
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
      setModalOpen(false);
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

  // Verify credential mutation
  const verifyMutation = useMutation({
    mutationFn: async (credentialId: string) => {
      const res = await api.post(`/credentials/${credentialId}/verify`);
      return res.data as VerifyResult;
    },
    onMutate: (id) => setVerifyingId(id),
    onSettled: () => {
      setVerifyingId(null);
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

  const handleSave = async (username: string, password: string) => {
    if (!selectedSite) return;

    if (existingCredential) {
      await updateMutation.mutateAsync({
        id: existingCredential.id,
        data: { username, password },
      });
    } else {
      await createMutation.mutateAsync({
        site_name: selectedSite.id,
        site_url: selectedSite.url,
        username,
        password,
      });
    }
  };

  const handleDelete = async () => {
    if (!existingCredential) return;
    await deleteMutation.mutateAsync(existingCredential.id);
  };

  return (
    <AppLayout>
      <div className="p-6 max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold text-white mb-2">Connections</h1>
        <p className="text-gray-400 mb-6">
          Connect your data sources to enable real-time property analysis.
        </p>

        <div className="space-y-4">
          {sites.map((site) => {
            const credential = getCredentialForSite(site.id);
            return (
              <ConnectionCard
                key={site.id}
                site={site}
                credential={credential}
                onConnect={() => handleConnect(site)}
                onVerify={() => credential && verifyMutation.mutate(credential.id)}
                isVerifying={verifyingId === credential?.id}
              />
            );
          })}
        </div>

        <div className="mt-8 p-4 bg-blue-900/20 border border-blue-700/50 rounded-lg">
          <h3 className="text-blue-400 font-medium mb-2 flex items-center gap-2">
            <Monitor size={18} />
            About Browser-Based Connections
          </h3>
          <p className="text-gray-400 text-sm">
            Some data sources require browser automation to access your existing
            subscriptions. These connections are slower than API-based sources (typically
            30-90 seconds per query) but provide access to premium data. Your credentials
            are encrypted using AES-256 and stored securely.
          </p>
        </div>

        {verifyMutation.isError && (
          <div className="mt-4 p-4 bg-red-900/20 border border-red-700/50 rounded-lg">
            <p className="text-red-400 text-sm">
              Verification failed. Please check your credentials and try again.
            </p>
          </div>
        )}
      </div>

      <CredentialModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        site={selectedSite}
        existingCredential={existingCredential}
        onSave={handleSave}
        onDelete={handleDelete}
        isLoading={createMutation.isPending || updateMutation.isPending || deleteMutation.isPending}
        error={
          createMutation.error?.message ||
          updateMutation.error?.message ||
          deleteMutation.error?.message ||
          null
        }
      />
    </AppLayout>
  );
}
