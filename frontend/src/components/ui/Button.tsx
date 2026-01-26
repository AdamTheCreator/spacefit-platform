import { forwardRef, type ReactNode, type ButtonHTMLAttributes } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ButtonVariant = 'primary' | 'secondary' | 'ghost';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visual variant. Defaults to "secondary" (outlined). */
  variant?: ButtonVariant;
  /** Size preset. Defaults to "md". */
  size?: ButtonSize;
  /** Icon rendered before the label. */
  iconLeft?: ReactNode;
  /** Icon rendered after the label. */
  iconRight?: ReactNode;
  /** Shows a spinner and disables the button. */
  loading?: boolean;
}

// ---------------------------------------------------------------------------
// Class maps
// ---------------------------------------------------------------------------

const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary: 'btn-industrial btn-industrial-primary',
  secondary: 'btn-industrial btn-industrial-secondary',
  ghost: 'btn-industrial btn-industrial-ghost',
};

const SIZE_CLASS: Record<ButtonSize, string> = {
  sm: 'btn-sm',
  md: '',
  lg: 'btn-lg',
};

// Icon sizes match the button size so icons stay proportional.
const ICON_SIZE: Record<ButtonSize, string> = {
  sm: 'w-3.5 h-3.5',
  md: 'w-4 h-4',
  lg: 'w-5 h-5',
};

// ---------------------------------------------------------------------------
// Spinner
// ---------------------------------------------------------------------------

function Spinner({ size }: { size: ButtonSize }) {
  const dim = ICON_SIZE[size];
  return (
    <span
      className={`${dim} rounded-full border-2 border-current border-t-transparent animate-spin flex-shrink-0`}
      aria-hidden
    />
  );
}

// ---------------------------------------------------------------------------
// Button
// ---------------------------------------------------------------------------

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'secondary',
      size = 'md',
      iconLeft,
      iconRight,
      loading = false,
      disabled,
      children,
      className,
      ...rest
    },
    ref,
  ) => {
    const classes = [
      VARIANT_CLASS[variant],
      SIZE_CLASS[size],
      className,
    ]
      .filter(Boolean)
      .join(' ');

    const isDisabled = disabled || loading;
    const iconCls = ICON_SIZE[size];

    return (
      <button
        ref={ref}
        className={classes}
        disabled={isDisabled}
        aria-busy={loading || undefined}
        {...rest}
      >
        {loading ? (
          <Spinner size={size} />
        ) : (
          iconLeft && <span className={`flex-shrink-0 ${iconCls} [&>svg]:w-full [&>svg]:h-full`}>{iconLeft}</span>
        )}
        {children}
        {!loading && iconRight && (
          <span className={`flex-shrink-0 ${iconCls} [&>svg]:w-full [&>svg]:h-full`}>{iconRight}</span>
        )}
      </button>
    );
  },
);

Button.displayName = 'Button';
