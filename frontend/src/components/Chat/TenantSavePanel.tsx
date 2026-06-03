import { useState } from 'react';
import { Link } from 'react-router-dom';
import { UserPlus, X, Check, ArrowRight, Loader2 } from 'lucide-react';
import { useTenantCandidates, useChatActions } from '../../stores/chatStore';
import {
  usePromoteTenantsFromVoid,
  type PromoteTenantsResult,
} from '../../hooks/useContacts';

/**
 * Surfaced beneath a void/matchmaker analysis: the recruitable tenants it found
 * (delivered via the `tenant_candidates` WS event) with a one-click "save these
 * as Contacts" — the void → contacts leg of the spine. Quiet by design: a single
 * soft card, no mascot, dismissible.
 */
export function TenantSavePanel() {
  const { tenantCandidates, tenantCandidatesSource } = useTenantCandidates();
  const { clearTenantCandidates } = useChatActions();
  const promote = usePromoteTenantsFromVoid();
  const [result, setResult] = useState<PromoteTenantsResult | null>(null);

  // Post-save confirmation (kept after the candidates are cleared from the store).
  if (result) {
    return (
      <div className="chat-stage px-4 py-2 animate-fade-in">
        <div className="pl-11 sm:pl-13">
          <div className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-[var(--accent)]/30 bg-[var(--accent-subtle)] text-sm text-industrial-secondary">
            <Check size={15} className="text-[var(--accent)]" />
            <span>
              Saved <strong className="text-industrial">{result.created}</strong>{' '}
              {result.created === 1 ? 'tenant' : 'tenants'} to Contacts
              {result.skipped > 0 && (
                <span className="text-industrial-muted">
                  {' '}
                  · {result.skipped} already there
                </span>
              )}
            </span>
            <Link
              to="/contacts"
              className="inline-flex items-center gap-1 font-medium text-[var(--accent)] hover:underline"
            >
              View <ArrowRight size={13} />
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (tenantCandidates.length === 0) return null;

  const preview = tenantCandidates.slice(0, 6);
  const extra = tenantCandidates.length - preview.length;

  const handleSave = async () => {
    try {
      const res = await promote.mutateAsync({
        tenants: tenantCandidates,
        source_address: tenantCandidatesSource,
      });
      setResult(res);
      clearTenantCandidates();
    } catch {
      // Error surfaced inline via promote.isError below.
    }
  };

  return (
    <div className="chat-stage px-4 py-2 animate-fade-in">
      <div className="pl-11 sm:pl-13">
        <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-3.5 max-w-xl">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2 text-sm text-industrial-secondary">
              <UserPlus size={15} className="text-[var(--accent)]" />
              <span>
                <strong className="text-industrial">{tenantCandidates.length}</strong>{' '}
                tenant {tenantCandidates.length === 1 ? 'idea' : 'ideas'} from this
                analysis
              </span>
            </div>
            <button
              onClick={clearTenantCandidates}
              className="text-industrial-muted hover:text-industrial-secondary transition-colors"
              aria-label="Dismiss tenant suggestions"
            >
              <X size={15} />
            </button>
          </div>

          <div className="mt-2 flex flex-wrap gap-1.5">
            {preview.map((t) => (
              <span
                key={t.name}
                className="px-2 py-0.5 rounded-md bg-[var(--bg-primary)] border border-[var(--border-subtle)] text-xs text-industrial-secondary"
              >
                {t.name}
              </span>
            ))}
            {extra > 0 && (
              <span className="px-2 py-0.5 text-xs text-industrial-muted">
                +{extra} more
              </span>
            )}
          </div>

          <div className="mt-3 flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={promote.isPending}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white text-sm font-medium transition-all disabled:opacity-60"
            >
              {promote.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <UserPlus size={14} />
              )}
              Save to Contacts
            </button>
            {promote.isError && (
              <span className="text-xs text-[var(--color-error)]">
                Couldn&apos;t save — try again.
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
