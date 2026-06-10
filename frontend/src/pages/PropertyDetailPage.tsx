import { useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { MapPin } from 'lucide-react';
import { AppLayout } from '../components/Layout/AppLayout';
import { AnalysisPlayground } from '../components/Playground/AnalysisPlayground';
import { useDocuments } from '../hooks/useDocuments';
import type { ExtractedFlyerData } from '../types/document';

// Property detail is an analysis workbench: it surfaces the documents linked to
// a property and hands them to the shared Playground. Header values are derived
// from real parsed-document data — never fabricated (see DESIGN.md "no mock").
export function PropertyDetailPage() {
  const { propertyId } = useParams<{ propertyId?: string }>();
  const { data: docList, isLoading } = useDocuments({ pageSize: 100 });

  // Real documents linked to this property via the denormalized property_id.
  const propertyDocs = useMemo(
    () => (docList?.items ?? []).filter((d) => d.property_id === propertyId),
    [docList, propertyId],
  );

  // Derive a header from a parsed document instead of inventing one.
  const headerInfo = propertyDocs
    .map((d) => (d.extracted_data as ExtractedFlyerData | null)?.property_info)
    .find((info) => info?.name || info?.address);
  const headerCityState = [headerInfo?.city, headerInfo?.state].filter(Boolean).join(', ');
  const subjectName = headerInfo?.name ?? null;
  const subjectAddress = [headerInfo?.address, headerCityState].filter(Boolean).join(', ') || null;
  const title = subjectName || 'Property analysis';

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        {/* Breadcrumb */}
        <div className="px-8 py-4 border-b border-[var(--border-subtle)] flex items-center gap-2 text-[13px] text-industrial-secondary">
          <Link to="/search" className="hover:text-industrial transition-colors">
            Search
          </Link>
          <span>/</span>
          <span className="text-industrial font-medium truncate">{title}</span>
        </div>

        <div className="px-8 py-7 max-w-[1400px]">
          {/* Header */}
          <div className="mb-6">
            <h1 className="font-display text-2xl font-semibold text-industrial tracking-tight">
              {title}
            </h1>
            {subjectAddress && (
              <div className="text-sm mt-1 text-industrial-secondary inline-flex items-center gap-1.5">
                <MapPin size={13} />
                {subjectAddress}
              </div>
            )}
          </div>

          {isLoading ? (
            <div className="flex items-center gap-2 py-12 justify-center">
              <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse" />
              <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse [animation-delay:200ms]" />
              <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse [animation-delay:400ms]" />
            </div>
          ) : (
            <AnalysisPlayground
              documents={propertyDocs}
              subjectName={subjectName}
              subjectAddress={subjectAddress}
              emptyState={
                <p className="text-sm text-industrial-muted leading-relaxed">
                  No parsed documents are linked to this property yet. Upload an offering memo or
                  flyer inside a{' '}
                  <Link to="/projects" className="text-[var(--accent)] hover:underline">
                    project
                  </Link>{' '}
                  to analyze it here.
                </p>
              }
            />
          )}
        </div>
      </div>
    </AppLayout>
  );
}

export default PropertyDetailPage;
