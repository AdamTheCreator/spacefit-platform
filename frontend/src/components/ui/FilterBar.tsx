import { Search } from 'lucide-react';
import type { ReactNode } from 'react';

// ---------------------------------------------------------------------------
// FilterBar — the standard workbench filter row: a token-styled search field,
// a set of filter controls (chips), and a trailing slot (result count, sort).
// Used above DataTables so every workbench surface gets the same dense,
// dark-mode-safe filter affordance instead of hand-rolling the layout.
// ---------------------------------------------------------------------------

export interface FilterBarProps {
  search?: {
    value: string;
    onChange: (value: string) => void;
    placeholder?: string;
  };
  /** Filter controls — typically <FilterChip>s. */
  children?: ReactNode;
  /** Right-aligned slot: result count, sort dropdown, etc. */
  trailing?: ReactNode;
  className?: string;
}

export function FilterBar({ search, children, trailing, className }: FilterBarProps) {
  return (
    <div className={`flex items-center gap-2 flex-wrap mb-4 ${className ?? ''}`}>
      {search && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-default)] min-w-[240px] max-w-[360px] flex-1">
          <Search size={15} className="text-industrial-muted flex-shrink-0" />
          <input
            value={search.value}
            onChange={(e) => search.onChange(e.target.value)}
            placeholder={search.placeholder ?? 'Search…'}
            className="bg-transparent outline-none border-none flex-1 text-[13px] text-industrial placeholder:text-industrial-muted"
          />
        </div>
      )}
      {children}
      {trailing != null && (
        <div className="ml-auto text-[12.5px] text-industrial-secondary tabular-nums">{trailing}</div>
      )}
    </div>
  );
}

export default FilterBar;
