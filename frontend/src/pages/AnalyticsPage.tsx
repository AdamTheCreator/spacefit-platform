import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { AppLayout } from '../components/Layout/AppLayout';
import { DataTable, type Column } from '../components/ui/DataTable';
import {
  usePipelineSummary,
  useCommissionForecast,
  useDeals,
} from '../hooks/useDeals';
import { formatCurrency, getStageConfig, type Deal } from '../types/deal';

// Stages that don't count as "open" pipeline.
const CLOSED_STAGES = new Set(['closed', 'passed', 'dead']);

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-industrial-secondary">
        {label}
      </div>
      <div className="font-display font-semibold text-[26px] text-industrial mt-1.5 leading-none tracking-tight">
        {value}
      </div>
    </div>
  );
}

function Loader() {
  return (
    <div className="flex items-center gap-2 py-20 justify-center">
      <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse" />
      <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse [animation-delay:200ms]" />
      <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse [animation-delay:400ms]" />
    </div>
  );
}

export function AnalyticsPage() {
  const summaryQuery = usePipelineSummary();
  const forecastQuery = useCommissionForecast(6);
  const dealsQuery = useDeals({ pageSize: 200 });

  const summary = summaryQuery.data;
  const forecast = forecastQuery.data;
  const deals = useMemo(() => dealsQuery.data?.items ?? [], [dealsQuery.data]);

  const loading = summaryQuery.isLoading || dealsQuery.isLoading;
  const errored =
    (summaryQuery.isError && !summary) || (dealsQuery.isError && !dealsQuery.data);

  // Real KPIs derived from live deals + pipeline summary.
  const openDeals = deals.filter((d) => !CLOSED_STAGES.has(d.stage));
  const weighted = openDeals.reduce(
    (s, d) => s + (d.commission_amount ?? 0) * (d.probability ?? 0) / 100,
    0,
  );
  const wonValue = deals
    .filter((d) => d.stage === 'closed')
    .reduce((s, d) => s + (d.commission_amount ?? 0), 0);
  const pipelineValue =
    summary?.total_potential_commission ??
    deals.reduce((s, d) => s + (d.commission_amount ?? 0), 0);
  const totalDeals = summary?.total_deals ?? deals.length;

  const maxMonth = Math.max(1, ...(forecast?.forecast ?? []).map((f) => f.expected_commission));
  const maxStage = Math.max(1, ...(summary?.stages ?? []).map((s) => s.total_commission));

  const columns: Column<Deal>[] = [
    {
      key: 'name', header: 'Deal',
      sortValue: (d) => d.name.toLowerCase(),
      render: (d) => (
        <div>
          <div className="text-sm font-medium text-industrial">{d.name}</div>
          {d.customer_name && <div className="text-xs text-industrial-secondary">{d.customer_name}</div>}
        </div>
      ),
    },
    {
      key: 'stage', header: 'Stage', width: 150,
      sortValue: (d) => d.stage,
      render: (d) => {
        const sc = getStageConfig(d.stage);
        return (
          <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${sc.color} bg-opacity-20 text-industrial`}>
            <span className={`w-1.5 h-1.5 rounded-full ${sc.color}`} />
            {sc.label}
          </span>
        );
      },
    },
    {
      key: 'prob', header: 'Probability', width: 120, align: 'right',
      sortValue: (d) => d.probability ?? 0,
      render: (d) => <span className="text-sm text-industrial-secondary">{d.probability}%</span>,
    },
    {
      key: 'commission', header: 'Commission', width: 140, align: 'right',
      sortValue: (d) => d.commission_amount ?? 0,
      render: (d) => <span className="text-sm text-industrial font-mono">{formatCurrency(d.commission_amount)}</span>,
    },
    {
      key: 'close', header: 'Close date', width: 130,
      sortValue: (d) => d.expected_close_date ?? null,
      render: (d) => <span className="text-sm text-industrial-secondary">{d.expected_close_date || '--'}</span>,
    },
  ];

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="px-8 py-6 grid gap-5 max-w-[1400px]">
          {/* Navy header strip */}
          <div className="relative bg-[var(--color-neutral-900)] text-white rounded-2xl px-7 py-5 flex items-center gap-5 overflow-hidden flex-wrap">
            <div className="absolute w-1 h-1 rounded-full bg-[#A7C7F7] opacity-70" style={{ top: 14, left: 40 }} />
            <div className="absolute w-1 h-1 rounded-full bg-[#E5B85C] opacity-80" style={{ top: 50, left: 110 }} />
            <div className="absolute w-[3px] h-[3px] rounded-full bg-[#A7C7F7] opacity-60" style={{ top: 30, right: 200 }} />
            <div className="absolute w-1 h-1 rounded-full bg-[#E5B85C] opacity-60" style={{ top: 62, right: 80 }} />

            <div className="flex-1 relative min-w-0">
              <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#E5B85C]">
                Insights engine
              </div>
              <h2 className="font-display text-[22px] text-white mt-1 tracking-tight">
                Pipeline analytics
              </h2>
            </div>
            <div className="flex gap-2 relative">
              <span className="inline-flex items-center px-3 py-1 rounded-full bg-white/10 border border-white/20 text-[11px] font-medium text-white">
                {totalDeals} {totalDeals === 1 ? 'deal' : 'deals'}
              </span>
              <span className="inline-flex items-center px-3 py-1 rounded-full bg-white/10 border border-white/20 text-[11px] font-medium text-white">
                {formatCurrency(pipelineValue)} pipeline
              </span>
            </div>
          </div>

          {loading ? (
            <Loader />
          ) : errored ? (
            <div className="card-industrial-static p-6 text-center text-sm text-industrial-secondary">
              Couldn&rsquo;t load analytics right now. Try again shortly.
            </div>
          ) : totalDeals === 0 ? (
            <div className="card-industrial-static p-10 text-center">
              <img
                src="/mascots/goose-planet.webp"
                alt=""
                aria-hidden="true"
                className="w-24 h-24 mx-auto mb-3 object-contain select-none"
                draggable={false}
              />
              <p className="text-sm text-industrial-secondary mb-1">No deals yet.</p>
              <p className="text-sm text-industrial-muted mb-4 max-w-sm mx-auto">
                Your pipeline analytics — value, weighted forecast, and stage breakdown — appear
                here once you start tracking deals.
              </p>
              <Link to="/pipeline" className="text-sm text-[var(--accent)] font-medium hover:underline">
                Go to pipeline
              </Link>
            </div>
          ) : (
            <>
              {/* Real KPIs */}
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3.5">
                <StatTile label="Pipeline value" value={formatCurrency(pipelineValue)} />
                <StatTile label="Weighted value" value={formatCurrency(weighted)} />
                <StatTile label="Open deals" value={String(openDeals.length)} />
                <StatTile label="Closed (won)" value={formatCurrency(wonValue)} />
                <StatTile label="6-mo forecast" value={formatCurrency(forecast?.total_forecast ?? 0)} />
              </div>

              {/* Commission forecast + by stage */}
              <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-5">
                <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-6">
                  <h3 className="font-display text-base font-semibold text-industrial mb-1">
                    Commission forecast
                  </h3>
                  <div className="text-xs text-industrial-secondary mb-4">
                    Expected commission by month · next 6 months
                  </div>
                  {forecast && forecast.forecast.length > 0 ? (
                    forecast.forecast.map((f) => (
                      <div key={f.month} className="mb-3 last:mb-0">
                        <div className="flex justify-between text-[13px] mb-1">
                          <span className="text-industrial font-medium">{f.month}</span>
                          <span className="text-industrial-secondary">
                            {formatCurrency(f.expected_commission)} · {f.deal_count}{' '}
                            {f.deal_count === 1 ? 'deal' : 'deals'}
                          </span>
                        </div>
                        <div className="bg-[var(--bg-tertiary)] h-2 rounded overflow-hidden">
                          <div
                            className="h-full rounded bg-[var(--accent)]"
                            style={{ width: `${(f.expected_commission / maxMonth) * 100}%` }}
                          />
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-industrial-muted">No forecast data yet.</p>
                  )}
                </div>

                <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-6">
                  <h3 className="font-display text-base font-semibold text-industrial mb-3.5">
                    Pipeline by stage
                  </h3>
                  {summary && summary.stages.length > 0 ? (
                    summary.stages.map((s) => {
                      const sc = getStageConfig(s.stage);
                      return (
                        <div key={s.stage} className="mb-3 last:mb-0">
                          <div className="flex justify-between text-[13px] mb-1">
                            <span className="text-industrial font-medium">{sc.label}</span>
                            <span className="text-industrial-secondary">
                              {s.count} · {formatCurrency(s.total_commission)}
                            </span>
                          </div>
                          <div className="bg-[var(--bg-tertiary)] h-2 rounded overflow-hidden">
                            <div
                              className={`h-full rounded ${sc.color}`}
                              style={{ width: `${(s.total_commission / maxStage) * 100}%` }}
                            />
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <p className="text-sm text-industrial-muted">No stage data yet.</p>
                  )}
                </div>
              </div>

              {/* Top deals */}
              <div className="pb-8">
                <h3 className="font-display text-[15px] font-semibold text-industrial mb-3">
                  Deals by commission
                </h3>
                <DataTable
                  columns={columns}
                  rows={deals}
                  rowKey={(d) => d.id}
                  initialSort={{ key: 'commission', dir: 'desc' }}
                  empty="No deals to show."
                />
              </div>
            </>
          )}
        </div>
      </div>
    </AppLayout>
  );
}

export default AnalyticsPage;
