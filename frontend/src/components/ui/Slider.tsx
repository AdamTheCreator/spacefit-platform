import { useId, type ReactNode } from 'react';

// ---------------------------------------------------------------------------
// Slider — a labeled range input for Playground-style parameter tuning.
// Renders a filled accent track + a live value badge. Quiet by default so it
// reads as a control, not chrome. See DESIGN.md → "Playground" pattern.
// ---------------------------------------------------------------------------

export interface SliderProps {
  label: ReactNode;
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step?: number;
  /** Suffix appended to the value badge, e.g. "mi". */
  unit?: string;
  /** Optional helper line under the control. */
  hint?: ReactNode;
  disabled?: boolean;
  id?: string;
}

export function Slider({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
  unit,
  hint,
  disabled,
  id,
}: SliderProps) {
  const reactId = useId();
  const inputId = id ?? reactId;
  // Fill the track up to the current value so the slider reads as filled-accent.
  const pct = max > min ? ((value - min) / (max - min)) * 100 : 0;

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label
          htmlFor={inputId}
          className="text-xs font-semibold text-industrial-secondary tracking-wide"
        >
          {label}
        </label>
        <span className="text-sm font-semibold text-industrial tabular-nums">
          {value}
          {unit ? <span className="text-industrial-muted font-medium">&nbsp;{unit}</span> : null}
        </span>
      </div>
      <input
        id={inputId}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-1.5 appearance-none rounded-full cursor-pointer accent-[var(--accent)] disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2"
        style={{
          background: `linear-gradient(to right, var(--accent) 0%, var(--accent) ${pct}%, var(--bg-tertiary) ${pct}%, var(--bg-tertiary) 100%)`,
        }}
      />
      {hint ? (
        <p className="mt-1.5 text-[11px] leading-snug text-industrial-muted">{hint}</p>
      ) : null}
    </div>
  );
}

export default Slider;
