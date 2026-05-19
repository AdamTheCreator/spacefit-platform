import { useNavigate } from 'react-router-dom';
import { X, ArrowRight } from 'lucide-react';
import { useSetupCards } from '../../hooks/useSetupCards';

/**
 * Dashboard section that surfaces deferred setup tasks (BYOK key,
 * preferences, imports, connectors) as dismissible cards. Replaces the
 * old forced onboarding wizard — each card is driven by real signal
 * and disappears automatically once the underlying task is done.
 */
export function SetupCards() {
  const navigate = useNavigate();
  const { cards, dismiss } = useSetupCards();

  if (cards.length === 0) return null;

  return (
    <section aria-label="Setup tasks">
      <div className="flex items-center justify-between mb-2.5">
        <h3 className="font-display text-[15px] font-semibold text-industrial">
          Get set up
        </h3>
        <span className="text-xs text-industrial-muted">
          {cards.length} task{cards.length === 1 ? '' : 's'} waiting
        </span>
      </div>
      <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((card) => (
          <div
            key={card.id}
            className={`relative rounded-xl border bg-[var(--bg-secondary)] p-4 transition-colors ${
              card.tone === 'attention'
                ? 'border-[#E5B85C]/40'
                : 'border-[var(--border-subtle)]'
            }`}
          >
            <button
              type="button"
              onClick={() => dismiss(card.id)}
              aria-label={`Dismiss ${card.title}`}
              className="absolute top-2 right-2 p-1 rounded-md text-industrial-muted hover:text-industrial hover:bg-[var(--bg-tertiary)] transition-colors"
            >
              <X size={14} />
            </button>
            <h4 className="font-display text-[14px] font-semibold text-industrial pr-6">
              {card.title}
            </h4>
            <p className="text-[12.5px] leading-[1.5] text-industrial-secondary mt-1.5 mb-3">
              {card.description}
            </p>
            <button
              type="button"
              onClick={() => navigate(card.href)}
              className="inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-[var(--accent)] hover:text-[var(--accent-hover)] transition-colors"
            >
              {card.cta}
              <ArrowRight size={13} />
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}

export default SetupCards;
