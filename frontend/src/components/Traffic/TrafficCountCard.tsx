import { Car, Gauge, Navigation, AlertCircle, Info } from 'lucide-react';
import { useTrafficCount, type TrafficMissReason } from '../../hooks/useTrafficCount';

interface TrafficCountCardProps {
  address: string;
}

const REASON_HEADING: Record<TrafficMissReason, string> = {
  ungeocodable: 'Address not on the map',
  no_station: 'No nearby traffic station',
  state_uncovered: 'State not covered yet',
};

const REASON_BODY: Record<TrafficMissReason, string> = {
  ungeocodable: 'We could not locate this address. Try a more complete street address.',
  no_station:
    'We cover this state, but no state-DOT traffic station is close enough to this property.',
  state_uncovered:
    'Traffic counts come from free state-DOT data; this state is not wired yet.',
};

function formatNumber(n: number): string {
  return n.toLocaleString('en-US');
}

/**
 * Property-level traffic count card. Shows the nearest official AADT (vehicles/day)
 * from free public state-DOT sources, or an honest empty state when no count is
 * available. The backend endpoint always returns 200, so we never surface an error
 * toast for a missing count — we render it as information.
 */
export function TrafficCountCard({ address }: TrafficCountCardProps) {
  const { data, isLoading, isError } = useTrafficCount(address);

  if (isLoading) {
    return (
      <div className="card-industrial-static p-4">
        <div className="flex items-center gap-2 text-sm text-industrial-secondary">
          <Gauge size={16} className="text-industrial-muted" />
          <span>Traffic counts</span>
        </div>
        <div className="mt-3 flex items-center gap-2 text-sm text-industrial-muted">
          <div className="w-4 h-4 rounded-full border-2 border-current border-t-transparent animate-spin" />
          Looking up nearby AADT…
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="card-industrial-static p-4">
        <div className="flex items-center gap-2 text-sm text-industrial-secondary">
          <Gauge size={16} className="text-industrial-muted" />
          <span>Traffic counts</span>
        </div>
        <div className="mt-3 flex items-start gap-2 text-sm text-industrial-secondary">
          <AlertCircle size={16} className="text-[var(--color-warning)] flex-shrink-0 mt-0.5" />
          Could not load traffic data. Try again in a moment.
        </div>
      </div>
    );
  }

  if (!data.found) {
    return (
      <div className="card-industrial-static p-4">
        <div className="flex items-center gap-2 text-sm text-industrial-secondary">
          <Gauge size={16} className="text-industrial-muted" />
          <span>Traffic counts</span>
        </div>
        <div className="mt-3 flex items-start gap-2 text-sm text-industrial-secondary">
          <Info size={16} className="text-industrial-muted flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-industrial">{REASON_HEADING[data.reason]}</p>
            <p className="mt-0.5 text-industrial-muted">{REASON_BODY[data.reason]}</p>
          </div>
        </div>
      </div>
    );
  }

  const { aadt, road, year, distance_mi, source, state } = data;

  return (
    <div className="card-industrial-static p-4">
      <div className="flex items-center gap-2 text-sm text-industrial-secondary">
        <Car size={16} className="text-[var(--accent)]" />
        <span>Traffic counts</span>
      </div>

      <div className="mt-3 flex items-baseline gap-2">
        <span className="font-display text-3xl font-semibold text-industrial tracking-tight">
          {formatNumber(aadt)}
        </span>
        <span className="text-sm text-industrial-muted">vehicles/day</span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-industrial-muted label-technical">
            Road
          </p>
          <p className="text-industrial font-medium truncate">{road}</p>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wide text-industrial-muted label-technical">
            Station
          </p>
          <p className="text-industrial font-medium">
            {source}
            {state ? ` · ${state}` : ''}
          </p>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wide text-industrial-muted label-technical">
            Year
          </p>
          <p className="text-industrial font-medium">{year ?? '—'}</p>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wide text-industrial-muted label-technical">
            Distance
          </p>
          <p className="text-industrial font-medium inline-flex items-center gap-1">
            <Navigation size={12} className="text-industrial-muted" />
            {distance_mi.toFixed(2)} mi
          </p>
        </div>
      </div>
    </div>
  );
}
