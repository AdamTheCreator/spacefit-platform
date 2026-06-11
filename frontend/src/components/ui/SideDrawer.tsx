import { useEffect, type ReactNode } from 'react';
import { X } from 'lucide-react';

// ---------------------------------------------------------------------------
// SideDrawer — the shared right-slide detail panel (DESIGN.md → "Parsed
// metadata → side drawers"). Backdrop + sticky header + scrollable body, Esc to
// close, token-styled. Used for record detail across workbench surfaces
// (Pipeline deals, Admin users) so detail opens beside the list instead of
// navigating away.
// ---------------------------------------------------------------------------

export interface SideDrawerProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  /** Tailwind max-width class for the panel. Default `max-w-lg`. */
  widthClass?: string;
  /** Optional actions rendered to the left of the close button. */
  headerRight?: ReactNode;
  children: ReactNode;
}

export function SideDrawer({
  open,
  onClose,
  title,
  widthClass = 'max-w-lg',
  headerRight,
  children,
}: SideDrawerProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 bg-black/50 z-40 animate-fade-in" onClick={onClose} aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        className={`fixed right-0 top-0 bottom-0 w-full ${widthClass} bg-[var(--bg-primary)] border-l border-[var(--border-default)] z-50 overflow-y-auto shadow-xl scrollbar-thin`}
      >
        <div className="sticky top-0 z-10 bg-[var(--bg-primary)] border-b border-[var(--border-subtle)] px-6 py-4 flex items-center justify-between gap-3">
          <div className="text-[15px] font-semibold text-industrial truncate min-w-0">{title}</div>
          <div className="flex items-center gap-1 flex-shrink-0">
            {headerRight}
            <button
              onClick={onClose}
              aria-label="Close"
              className="p-1.5 rounded-lg text-industrial-secondary hover:bg-[var(--bg-tertiary)] hover:text-industrial transition-colors"
            >
              <X size={18} />
            </button>
          </div>
        </div>
        {children}
      </div>
    </>
  );
}

export default SideDrawer;
