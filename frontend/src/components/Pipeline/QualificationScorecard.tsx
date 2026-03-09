import type { Property } from '../../types/deal';

interface QualificationScorecardProps {
  property: Property;
  compact?: boolean;
}

interface ScoreDimension {
  label: string;
  score: number;
  maxScore: number;
  key: string;
}

export function QualificationScorecard({ property, compact = false }: QualificationScorecardProps) {
  const score = property.qualification_score;
  const data = property.qualification_data as Record<string, unknown> | undefined;

  if (score == null) {
    return compact ? null : (
      <div className="bg-[var(--bg-elevated)] border border-[var(--border)] rounded-lg p-4 text-center text-[var(--text-secondary)] text-sm">
        Not yet scored. Run qualification to generate a scorecard.
      </div>
    );
  }

  const dimensions: ScoreDimension[] = [
    { label: 'Market Fit', score: (data?.market_fit as number) ?? 0, maxScore: 25, key: 'market_fit' },
    { label: 'Product Fit', score: (data?.product_fit as number) ?? 0, maxScore: 15, key: 'product_fit' },
    { label: 'Intersection', score: (data?.intersection as number) ?? 0, maxScore: 20, key: 'intersection' },
    { label: 'Demographics', score: (data?.demographics as number) ?? 0, maxScore: 20, key: 'demographics' },
    { label: 'Pricing', score: (data?.pricing as number) ?? 0, maxScore: 20, key: 'pricing' },
  ];

  const recommendation = (data?.recommendation as string) ?? 'pass';
  const recColor = recommendation === 'pursue' ? 'text-green-400' :
                    recommendation === 'save_as_comp' ? 'text-yellow-400' : 'text-red-400';
  const recLabel = recommendation === 'pursue' ? 'Pursue' :
                   recommendation === 'save_as_comp' ? 'Save as Comp' : 'Pass';

  const scoreColor = score >= 60 ? 'text-green-400' : score >= 30 ? 'text-yellow-400' : 'text-red-400';
  const ringColor = score >= 60 ? 'stroke-green-400' : score >= 30 ? 'stroke-yellow-400' : 'stroke-red-400';

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <span className={`font-mono font-bold text-sm ${scoreColor}`}>{score}</span>
        <span className={`text-xs ${recColor}`}>{recLabel}</span>
      </div>
    );
  }

  return (
    <div className="bg-[var(--bg-elevated)] border border-[var(--border)] rounded-lg p-5">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-sm font-medium text-[var(--text-primary)]">Qualification Score</h3>
          <span className={`text-xs font-medium ${recColor}`}>{recLabel}</span>
        </div>

        {/* Score ring */}
        <div className="relative w-16 h-16">
          <svg className="w-16 h-16 -rotate-90" viewBox="0 0 64 64">
            <circle cx="32" cy="32" r="28" fill="none" strokeWidth="4"
              className="stroke-[var(--border)]" />
            <circle cx="32" cy="32" r="28" fill="none" strokeWidth="4"
              className={ringColor}
              strokeDasharray={`${(score / 100) * 175.9} 175.9`}
              strokeLinecap="round" />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className={`text-lg font-bold font-mono ${scoreColor}`}>{score}</span>
          </div>
        </div>
      </div>

      {/* Dimension bars */}
      <div className="space-y-2.5">
        {dimensions.map(dim => {
          const pct = dim.maxScore > 0 ? (dim.score / dim.maxScore) * 100 : 0;
          return (
            <div key={dim.key}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-[var(--text-secondary)]">{dim.label}</span>
                <span className="text-[var(--text-primary)] font-mono">{dim.score}/{dim.maxScore}</span>
              </div>
              <div className="h-1.5 bg-[var(--bg-secondary)] rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    pct >= 70 ? 'bg-green-500' : pct >= 40 ? 'bg-yellow-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
