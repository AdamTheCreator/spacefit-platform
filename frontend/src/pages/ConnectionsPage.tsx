import { useState } from 'react';
import { AppLayout } from '../components/Layout';
import {
  Upload,
  BarChart3,
  Building2,
  Users,
  FileText,
} from 'lucide-react';
import { CredentialModal } from '../components/Connections/CredentialModal';

interface DataSource {
  id: string;
  name: string;
  description: string;
  importType: string;
  icon: React.ReactNode;
  importCount: number;
}

const DATA_SOURCES: DataSource[] = [
  {
    id: 'costar',
    name: 'CoStar',
    description: 'Lease comps, tenant rosters, and property details',
    importType: 'CSV',
    icon: <Building2 size={24} className="text-purple-400" />,
    importCount: 0,
  },
  {
    id: 'placer',
    name: 'Placer.ai',
    description: 'Foot traffic, visitor demographics, and trade area analytics',
    importType: 'PDF',
    icon: <Users size={24} className="text-green-400" />,
    importCount: 0,
  },
  {
    id: 'siteusa',
    name: 'SiteUSA',
    description: 'Vehicle traffic counts and enhanced demographics',
    importType: 'CSV',
    icon: <BarChart3 size={24} className="text-blue-400" />,
    importCount: 0,
  },
];

function DataSourceCard({
  source,
  onImport,
}: {
  source: DataSource;
  onImport: () => void;
}) {
  return (
    <div className="card-industrial">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-[var(--bg-tertiary)] border border-industrial-subtle flex items-center justify-center">
            {source.icon}
          </div>
          <div>
            <h3 className="font-mono text-sm font-medium text-industrial flex items-center gap-2">
              {source.name}
              <span className="font-mono text-[10px] uppercase tracking-wide bg-[var(--bg-tertiary)] text-industrial-muted px-2 py-0.5 border border-industrial-subtle">
                {source.importType}
              </span>
            </h3>
            <p className="font-mono text-xs text-industrial-muted">{source.description}</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <span className="flex items-center gap-2 font-mono text-xs text-industrial-muted">
            <FileText size={14} />
            {source.importCount} imports
          </span>
          <button onClick={onImport} className="btn-industrial-primary">
            <Upload size={14} />
            Import {source.importType}
          </button>
        </div>
      </div>
    </div>
  );
}

export function ConnectionsPage() {
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedSource, setSelectedSource] = useState<string | null>(null);

  const handleImport = (sourceId: string) => {
    setSelectedSource(sourceId);
    setModalOpen(true);
  };

  return (
    <AppLayout>
      <div className="p-6 max-w-4xl mx-auto bg-industrial min-h-full">
        <h1 className="font-mono text-lg font-bold tracking-tight text-industrial mb-2">Data Sources</h1>
        <p className="font-mono text-xs text-industrial-muted mb-6">
          Import data from your existing subscriptions to power AI analysis.
        </p>

        <div className="space-y-4">
          {DATA_SOURCES.map((source) => (
            <DataSourceCard
              key={source.id}
              source={source}
              onImport={() => handleImport(source.id)}
            />
          ))}
        </div>

        <div className="mt-8 p-4 bg-[var(--accent)]/5 border border-[var(--accent)]/30">
          <h3 className="font-mono text-xs font-semibold uppercase tracking-wide text-[var(--accent)] mb-2 flex items-center gap-2">
            <Upload size={16} />
            How Imports Work
          </h3>
          <p className="font-mono text-xs text-industrial-secondary">
            Export data from your CoStar, Placer.ai, or SiteUSA account, then upload the file here.
            Perigee parses and structures the data so the AI can use it during analysis.
            No passwords or login credentials are stored.
          </p>
        </div>
      </div>

      <CredentialModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        sourceId={selectedSource}
      />
    </AppLayout>
  );
}
