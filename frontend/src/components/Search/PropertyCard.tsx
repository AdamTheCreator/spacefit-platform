import { useNavigate } from 'react-router-dom';
import { Star } from 'lucide-react';

export interface PropertyCardData {
  id: number;
  addr: string;
  city: string;
  price: string;
  cap: string;
  score: number;
  year: number;
  units: number;
  grad: string;
  delta?: string; // e.g. "+$240k"
  age?: string;   // e.g. "3d ago"
}

function scorePill(score: number): { bg: string; fg: string } {
  if (score >= 85) return { bg: '#E3F1E5', fg: '#2F7A3B' };  // green
  if (score >= 80) return { bg: '#FBEFC8', fg: '#8A6417' };  // gold
  return { bg: 'rgba(15,27,45,0.88)', fg: '#FFFFFF' };        // navy
}

export function PropertyCard({
  p,
  compact,
  onClick,
}: {
  p: PropertyCardData;
  compact?: boolean;
  onClick?: () => void;
}) {
  const navigate = useNavigate();
  const handleClick = () => {
    if (onClick) onClick();
    else navigate('/projects');
  };
  const pill = scorePill(p.score);
  return (
    <button
      type="button"
      onClick={handleClick}
      className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl overflow-hidden text-left w-full transition-all hover:-translate-y-0.5 hover:shadow-md"
    >
      <div
        className="relative overflow-hidden"
        style={{ aspectRatio: compact ? '16/7' : '16/10', background: p.grad }}
      >
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage:
              'repeating-linear-gradient(45deg, rgba(255,255,255,0.12) 0 6px, transparent 6px 12px)',
          }}
        />
        <span
          className="absolute top-3 left-3 inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-semibold"
          style={{ background: pill.bg, color: pill.fg }}
        >
          Score {p.score}
        </span>
        <button
          type="button"
          aria-label="Save to watchlist"
          onClick={(e) => {
            e.stopPropagation();
          }}
          className="absolute top-3 right-3 w-8 h-8 rounded-lg bg-white/90 hover:bg-white flex items-center justify-center text-industrial transition-colors"
        >
          <Star size={14} />
        </button>
      </div>
      <div className="p-4">
        <div className="flex justify-between items-start gap-2.5">
          <div className="min-w-0 flex-1">
            <div className="font-display text-[15px] font-semibold text-industrial">{p.addr}</div>
            <div className="text-xs text-industrial-secondary mt-0.5">
              {p.city} · {p.units} units · {p.year}
            </div>
          </div>
          <div className="font-display text-base font-bold text-industrial shrink-0">{p.price}</div>
        </div>
        <div className="flex gap-3 mt-3 pt-3 border-t border-[var(--border-subtle)] text-xs text-industrial-secondary">
          <div>
            <span className="text-industrial font-semibold">{p.cap}</span> cap
          </div>
          <div>
            <span className="text-[var(--color-success)] font-semibold">{p.delta ?? '+$240k'}</span>{' '}
            NOI est.
          </div>
          <div className="ml-auto">{p.age ?? '3d ago'}</div>
        </div>
      </div>
    </button>
  );
}
