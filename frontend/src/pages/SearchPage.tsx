import { useState, useRef, useEffect, useMemo } from 'react';
import { Upload, Sparkles } from 'lucide-react';
import { AppLayout } from '../components/Layout/AppLayout';
import { FilterBar } from '../components/ui/FilterBar';
import { FilterChip } from './contacts/ui';
import { useCompanies } from '../hooks/useContacts';
import {
  useListings,
  useImportListings,
  useMatchListings,
  type Listing,
  type MatchedListing,
} from '../hooks/useListings';

// ---------------------------------------------------------------------------
// Formatting helpers (inline money / percent — fine per the design rules).
// ---------------------------------------------------------------------------

function formatMoney(price: number | null): string | null {
  if (price == null) return null;
  return `$${price.toLocaleString('en-US')}`;
}

function formatSf(sf: number | null): string | null {
  if (sf == null) return null;
  return `${sf.toLocaleString('en-US')} SF`;
}

function formatCap(cap: number | null): string | null {
  if (cap == null) return null;
  // Stored as a percent value (e.g. 6.4 → "6.4% cap").
  return `${cap}% cap`;
}

function listingTitle(l: Listing): string {
  if (l.address) return l.address;
  const cityState = [l.city, l.state].filter(Boolean).join(', ');
  return cityState || 'Untitled listing';
}

function listingLocation(l: Listing): string | null {
  // When the address is the title, show city/state as the secondary line.
  if (!l.address) return null;
  const cityState = [l.city, l.state].filter(Boolean).join(', ');
  return cityState || null;
}

/** Score badge token mapping: ≥75 green, 40–74 amber, <40 muted/red. */
function scoreTone(score: number): { bg: string; fg: string } {
  if (score >= 75)
    return { bg: 'var(--color-success-light)', fg: 'var(--color-success)' };
  if (score >= 40)
    return { bg: 'var(--color-warning-light)', fg: 'var(--color-warning)' };
  return { bg: 'var(--color-error-light)', fg: 'var(--color-error)' };
}

/** Compare nullable numerics, always sorting nulls last. */
function cmpNullable(a: number | null, b: number | null, dir: 1 | -1): number {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  return (a - b) * dir;
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function SearchPage() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedCompanyId, setSelectedCompanyId] = useState('');
  const [toast, setToast] = useState<string | null>(null);
  const [q, setQ] = useState('');
  const [assetType, setAssetType] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState('fit');

  const companies = useCompanies();
  const listings = useListings();
  const importListings = useImportListings();
  const matchListings = useMatchListings();

  const listingCount = listings.data?.length ?? 0;
  const result = matchListings.data;

  const assetTypes = useMemo(() => {
    const s = new Set<string>();
    (result?.matches ?? []).forEach((m) => {
      if (m.listing.asset_type) s.add(m.listing.asset_type);
    });
    return [...s].sort().map((a) => ({ value: a, label: a }));
  }, [result]);

  const displayed = useMemo(() => {
    let arr = result?.matches ?? [];
    if (q) {
      const needle = q.toLowerCase();
      arr = arr.filter((m) => {
        const l = m.listing;
        return [l.address, l.city, l.state, l.asset_type]
          .filter(Boolean)
          .join(' ')
          .toLowerCase()
          .includes(needle);
      });
    }
    if (assetType) arr = arr.filter((m) => m.listing.asset_type === assetType);
    const sorted = [...arr];
    sorted.sort((a, b) => {
      switch (sortKey) {
        case 'price_asc':
          return cmpNullable(a.listing.price, b.listing.price, 1);
        case 'price_desc':
          return cmpNullable(a.listing.price, b.listing.price, -1);
        case 'size_desc':
          return cmpNullable(a.listing.size_sf, b.listing.size_sf, -1);
        case 'cap_desc':
          return cmpNullable(a.listing.cap_rate, b.listing.cap_rate, -1);
        default:
          return b.fit_score - a.fit_score;
      }
    });
    return sorted;
  }, [result, q, assetType, sortKey]);

  const onFilePicked = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    // Reset so picking the same file again re-triggers onChange.
    e.target.value = '';
    if (!file) return;
    importListings.mutate(file, {
      onSuccess: (r) =>
        setToast(
          `Imported ${r.imported} listings${r.failed ? ` · ${r.failed} failed` : ''}`,
        ),
      onError: () => setToast('Import failed — check the file format'),
    });
  };

  const onPickClient = (companyId: string) => {
    setSelectedCompanyId(companyId);
    if (companyId) matchListings.mutate({ company_id: companyId });
  };

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="px-8 py-6 max-w-[1100px] mx-auto">
          {/* Header */}
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between mb-6">
            <div>
              <h1 className="font-display text-2xl font-semibold text-[var(--text-primary)]">
                Find properties
              </h1>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                Score the market against a client&rsquo;s buy-box
              </p>
            </div>
            <div className="flex items-center gap-3">
              {listingCount > 0 && (
                <span className="text-xs text-[var(--text-muted)] whitespace-nowrap">
                  {listingCount} {listingCount === 1 ? 'listing' : 'listings'} on file
                </span>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.xlsx"
                aria-label="Import listings file"
                className="hidden"
                onChange={onFilePicked}
              />
              <button
                className="btn-industrial-secondary text-sm px-4 py-2 rounded-lg flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={importListings.isPending}
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="h-4 w-4" />
                {importListings.isPending ? 'Importing…' : 'Import listings'}
              </button>
            </div>
          </div>

          {/* Client picker */}
          <div className="card-industrial-static p-4 mb-6">
            <label
              htmlFor="client-picker"
              className="block text-sm font-medium text-[var(--text-primary)] mb-1.5"
            >
              Score for client
            </label>
            <select
              id="client-picker"
              value={selectedCompanyId}
              onChange={(e) => onPickClient(e.target.value)}
              disabled={listingCount === 0 || companies.isLoading}
              className="input-industrial w-full sm:max-w-md disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <option value="">
                {companies.isLoading
                  ? 'Loading clients…'
                  : (companies.data?.length ?? 0) === 0
                    ? 'No clients yet'
                    : 'Select a client…'}
              </option>
              {companies.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          {/* Body */}
          {listingCount === 0 && !listings.isLoading ? (
            <EmptyState />
          ) : matchListings.isPending ? (
            <MatchingLoader />
          ) : matchListings.isError ? (
            <SoftNote>
              Couldn&rsquo;t score these listings. Pick the client again to retry.
            </SoftNote>
          ) : result ? (
            result.matches.length === 0 ? (
              <SoftNote>
                No matches for{' '}
                <span className="font-medium text-[var(--text-primary)]">
                  {result.client_name}
                </span>{' '}
                yet — try importing more listings or a different client.
              </SoftNote>
            ) : (
              <>
                <div className="mb-3 text-sm text-[var(--text-secondary)]">
                  Scored for{' '}
                  <span className="text-[var(--text-primary)] font-medium">
                    {result.client_name}
                  </span>
                </div>
                <FilterBar
                  search={{ value: q, onChange: setQ, placeholder: 'Filter by address, city, type…' }}
                  trailing={
                    <div className="flex items-center gap-3">
                      <span>
                        {displayed.length} of {result.matches.length}
                      </span>
                      <select
                        aria-label="Sort listings"
                        value={sortKey}
                        onChange={(e) => setSortKey(e.target.value)}
                        className="text-[12.5px] rounded-lg border border-[var(--border-default)] bg-[var(--bg-elevated)] text-industrial px-2 py-1 cursor-pointer focus:outline-none focus:border-[var(--accent)]"
                      >
                        <option value="fit">Best fit</option>
                        <option value="price_asc">Price ↑</option>
                        <option value="price_desc">Price ↓</option>
                        <option value="size_desc">Largest</option>
                        <option value="cap_desc">Highest cap</option>
                      </select>
                    </div>
                  }
                >
                  {assetTypes.length > 1 && (
                    <FilterChip
                      label="Type"
                      value={assetType}
                      onChange={setAssetType}
                      options={assetTypes}
                      allLabel="All types"
                    />
                  )}
                </FilterBar>
                <div className="flex flex-col gap-3 pb-8">
                  {displayed.length === 0 ? (
                    <SoftNote>No listings match those filters.</SoftNote>
                  ) : (
                    displayed.map((m) => <MatchCard key={m.listing.id} match={m} />)
                  )}
                </div>
              </>
            )
          ) : (
            <SoftNote>
              <span className="inline-flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-[var(--accent)]" />
                Pick a client above to score your {listingCount} imported{' '}
                {listingCount === 1 ? 'listing' : 'listings'} against their buy-box.
              </span>
            </SoftNote>
          )}
        </div>
      </div>

      <Toast msg={toast} onClose={() => setToast(null)} />
    </AppLayout>
  );
}

// ---------------------------------------------------------------------------
// Result card
// ---------------------------------------------------------------------------

function MatchCard({ match }: { match: MatchedListing }) {
  const { listing: l, fit_score, rationale, flags } = match;
  const tone = scoreTone(fit_score);
  const location = listingLocation(l);
  const facts = [
    l.asset_type,
    formatSf(l.size_sf),
    formatMoney(l.price),
    formatCap(l.cap_rate),
  ].filter(Boolean) as string[];

  return (
    <div className="card-industrial p-5 flex gap-4">
      {/* Score badge */}
      <div
        className="flex flex-col items-center justify-center rounded-xl w-16 h-16 shrink-0"
        style={{ background: tone.bg, color: tone.fg }}
      >
        <span className="font-display text-xl font-bold leading-none">{fit_score}</span>
        <span className="text-[10px] font-semibold uppercase tracking-wide mt-0.5">
          fit
        </span>
      </div>

      {/* Body */}
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] truncate">
            {listingTitle(l)}
          </h3>
          {l.listing_url && (
            <a
              href={l.listing_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-[var(--accent)] hover:underline shrink-0"
            >
              View listing
            </a>
          )}
        </div>
        {location && (
          <div className="text-xs text-[var(--text-muted)] mt-0.5">{location}</div>
        )}

        {facts.length > 0 && (
          <div className="text-[13px] text-[var(--text-secondary)] mt-2">
            {facts.join(' · ')}
          </div>
        )}

        {rationale && (
          <p className="text-sm text-[var(--text-secondary)] mt-2 leading-relaxed">
            {rationale}
          </p>
        )}

        {flags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-3">
            {flags.map((flag, i) => (
              <span
                key={i}
                className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-[var(--bg-tertiary)] text-[var(--text-secondary)]"
              >
                {flag}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// States
// ---------------------------------------------------------------------------

function EmptyState() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const importListings = useImportListings();

  const onFilePicked = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (file) importListings.mutate(file);
  };

  return (
    <div className="text-center py-16">
      <img
        src="/mascots/goose-planet.webp"
        alt=""
        aria-hidden="true"
        className="w-28 h-28 mx-auto mb-3 object-contain select-none"
        draggable={false}
      />
      <p className="text-sm text-[var(--text-secondary)] mb-1">
        No listings on file yet.
      </p>
      <p className="text-sm text-[var(--text-muted)] mb-4 max-w-sm mx-auto">
        Import a CSV or Excel of for-sale properties and the matcher will rank them
        against any client&rsquo;s buy-box.
      </p>
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,.xlsx"
        aria-label="Import listings file"
        className="hidden"
        onChange={onFilePicked}
      />
      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={importListings.isPending}
        className="text-sm text-[var(--accent)] font-medium hover:underline disabled:opacity-50"
      >
        {importListings.isPending ? 'Importing…' : 'Import listings'}
      </button>
    </div>
  );
}

function MatchingLoader() {
  return (
    <div className="flex items-center gap-2 py-16 justify-center">
      <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse" />
      <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse [animation-delay:200ms]" />
      <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse [animation-delay:400ms]" />
      <span className="ml-2 text-sm text-[var(--text-muted)]">Scoring listings…</span>
    </div>
  );
}

function SoftNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="card-industrial-static p-6 text-center text-sm text-[var(--text-secondary)]">
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Toast (self-contained; auto-dismisses)
// ---------------------------------------------------------------------------

function Toast({ msg, onClose }: { msg: string | null; onClose: () => void }) {
  useEffect(() => {
    if (!msg) return;
    const t = setTimeout(onClose, 4000);
    return () => clearTimeout(t);
  }, [msg, onClose]);

  if (!msg) return null;
  return (
    <div
      role="status"
      className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-lg bg-[var(--color-neutral-900)] text-white text-sm shadow-lg animate-scale-in"
    >
      {msg}
    </div>
  );
}

export default SearchPage;
