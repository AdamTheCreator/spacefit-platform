import { Lightbulb, X } from 'lucide-react';

interface PromoteNudgeProps {
  onPromote: () => void;
  onDismiss: () => void;
}

/**
 * Dismissible cream banner nudging the user to attach a free-form chat to a
 * project once the conversation has built up some substance. Visibility is
 * decided by the caller (see `shouldShowNudge` in `promoteChat.ts`).
 */
export function PromoteNudge({ onPromote, onDismiss }: PromoteNudgeProps) {
  return (
    <div className="flex items-center gap-3 px-4 py-3.5 rounded-xl border border-[var(--color-gold)]/40 bg-[var(--bg-cream)]">
      <Lightbulb size={18} className="flex-shrink-0 text-[var(--color-gold)]" />
      <p className="flex-1 text-[13px] text-industrial leading-snug">
        <span className="font-semibold">This is getting interesting.</span>{' '}
        <span className="text-industrial-secondary">
          Save this chat to a project to ground future answers in your uploaded
          data.
        </span>
      </p>
      <button
        onClick={onPromote}
        className="flex-shrink-0 px-3 py-1.5 rounded-lg text-[13px] font-semibold bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] transition-colors"
      >
        Save to project
      </button>
      <button
        onClick={onDismiss}
        className="flex-shrink-0 p-1.5 rounded-lg text-industrial-muted hover:bg-[var(--bg-tertiary)] transition-colors"
        aria-label="Dismiss"
      >
        <X size={15} />
      </button>
    </div>
  );
}
