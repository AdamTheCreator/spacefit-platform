import type { ReactNode } from 'react';

// ---------------------------------------------------------------------------
// SegmentedControl — a compact single-select pill row. Familiar pattern
// (Jakob's Law) for switching between a small set of mutually-exclusive
// options: analysis type, use-case focus, table view modes, etc.
// ---------------------------------------------------------------------------

export interface SegmentedOption<T extends string> {
  value: T;
  label: ReactNode;
  /** Optional leading icon. */
  icon?: ReactNode;
}

export interface SegmentedControlProps<T extends string> {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  /** Accessible label for the group. */
  ariaLabel?: string;
  /** Stretch each segment to equal width. */
  fill?: boolean;
  size?: 'sm' | 'md';
  disabled?: boolean;
}

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  ariaLabel,
  fill = false,
  size = 'md',
  disabled,
}: SegmentedControlProps<T>) {
  const pad = size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3 py-1.5 text-[13px]';

  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className="inline-flex items-center gap-0.5 rounded-lg bg-[var(--bg-tertiary)] p-0.5 border border-[var(--border-subtle)]"
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={disabled}
            onClick={() => onChange(opt.value)}
            className={`
              inline-flex items-center justify-center gap-1.5 rounded-md font-medium whitespace-nowrap
              transition-colors ${pad} ${fill ? 'flex-1' : ''}
              ${
                active
                  ? 'bg-[var(--bg-elevated)] text-industrial shadow-sm'
                  : 'text-industrial-secondary hover:text-industrial'
              }
              disabled:opacity-50 disabled:cursor-not-allowed
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]
            `}
          >
            {opt.icon ? <span className="flex-shrink-0 [&>svg]:w-3.5 [&>svg]:h-3.5">{opt.icon}</span> : null}
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

export default SegmentedControl;
