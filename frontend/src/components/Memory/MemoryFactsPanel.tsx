import {
  useApproveFact,
  useArchiveFact,
  useRejectFact,
  useUserFacts,
  type FactStatus,
  type UserFact,
} from '../../hooks/useUserFacts';

interface MemoryFactsPanelProps {
  statusFilter?: FactStatus;
  emptyHint?: string;
  showApproveControls?: boolean;
}

const CATEGORY_LABEL: Record<string, string> = {
  deal_prefs: 'Deal preferences',
  geography: 'Geography',
  business_model: 'Business model',
  personal: 'Personal',
  other: 'Other',
};

export function MemoryFactsPanel({
  statusFilter,
  emptyHint,
  showApproveControls = true,
}: MemoryFactsPanelProps) {
  const { data: facts, isLoading } = useUserFacts(statusFilter);
  const approveFact = useApproveFact();
  const rejectFact = useRejectFact();
  const archiveFact = useArchiveFact();

  if (isLoading) {
    return (
      <div className="text-sm text-industrial-muted">Loading memory…</div>
    );
  }
  if (!facts || facts.length === 0) {
    return (
      <div className="text-sm text-industrial-muted">
        {emptyHint || 'No memory yet — keep chatting and Space Goose will start learning your preferences.'}
      </div>
    );
  }

  return (
    <ul className="space-y-2">
      {facts.map((fact: UserFact) => (
        <li
          key={fact.id}
          className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <p className="text-sm text-industrial">{fact.text}</p>
              <div className="mt-1 flex items-center gap-2 text-[11px] text-industrial-muted uppercase tracking-wide">
                <span>{CATEGORY_LABEL[fact.category] || fact.category}</span>
                {fact.status !== 'pending' && (
                  <span className="rounded bg-[var(--bg-tertiary)] px-1.5 py-0.5">
                    {fact.status}
                  </span>
                )}
                <span>· confidence {Math.round(fact.confidence * 100)}%</span>
              </div>
            </div>
            {showApproveControls && fact.status === 'pending' && (
              <div className="flex flex-shrink-0 items-center gap-1">
                <button
                  type="button"
                  className="rounded-md border border-[var(--border-subtle)] px-2 py-1 text-xs hover:bg-[var(--bg-tertiary)]"
                  onClick={() => approveFact.mutate(fact.id)}
                  disabled={approveFact.isPending}
                >
                  Approve
                </button>
                <button
                  type="button"
                  className="rounded-md border border-[var(--border-subtle)] px-2 py-1 text-xs hover:bg-[var(--bg-tertiary)]"
                  onClick={() => rejectFact.mutate(fact.id)}
                  disabled={rejectFact.isPending}
                >
                  Reject
                </button>
              </div>
            )}
            {fact.status === 'approved' && (
              <button
                type="button"
                className="rounded-md border border-[var(--border-subtle)] px-2 py-1 text-xs text-industrial-muted hover:text-industrial hover:bg-[var(--bg-tertiary)]"
                onClick={() => archiveFact.mutate(fact.id)}
                disabled={archiveFact.isPending}
                title="Archive this fact"
              >
                Remove
              </button>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
