import { AppLayout } from '../components/Layout';
import { Upload } from 'lucide-react';
import { ImportUploadCard } from '../components/Imports/ImportUploadCard';

const SOURCES = ['costar', 'placer', 'siteusa'] as const;

export function ConnectionsPage() {
  return (
    <AppLayout>
      <div className="p-6 max-w-4xl mx-auto bg-industrial min-h-full">
        <h1 className="font-mono text-lg font-bold tracking-tight text-industrial mb-2">
          Data Library
        </h1>
        <p className="font-mono text-xs text-industrial-muted mb-6">
          Upload data that you want to reuse across multiple projects. For
          deal-specific imports, upload them directly inside the project instead.
        </p>

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
