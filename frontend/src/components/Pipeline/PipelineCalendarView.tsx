import { useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { Deal } from '../../types/deal';
import { getStageConfig, formatCurrency } from '../../types/deal';
import { usePipelineStore } from '../../stores/pipelineStore';

interface PipelineCalendarViewProps {
  deals: Deal[];
}

function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function endOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth() + 1, 0);
}

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

interface CalendarDeal {
  deal: Deal;
  date: Date;
  dateType: 'expected_close' | 'lease_start';
}

export function PipelineCalendarView({ deals }: PipelineCalendarViewProps) {
  const { openDetailDrawer } = usePipelineStore();
  const [currentMonth, setCurrentMonth] = useState(() => startOfMonth(new Date()));

  const calendarDeals = useMemo(() => {
    const items: CalendarDeal[] = [];
    for (const deal of deals) {
      if (deal.expected_close_date) {
        items.push({ deal, date: new Date(deal.expected_close_date), dateType: 'expected_close' });
      }
      if (deal.lease_start_date) {
        items.push({ deal, date: new Date(deal.lease_start_date), dateType: 'lease_start' });
      }
    }
    return items;
  }, [deals]);

  // Build calendar grid
  const calendarDays = useMemo(() => {
    const first = startOfMonth(currentMonth);
    const last = endOfMonth(currentMonth);
    const startDay = first.getDay(); // 0 = Sunday
    const days: (Date | null)[] = [];

    // Leading empty cells
    for (let i = 0; i < startDay; i++) days.push(null);

    // Days of month
    for (let d = 1; d <= last.getDate(); d++) {
      days.push(new Date(currentMonth.getFullYear(), currentMonth.getMonth(), d));
    }

    return days;
  }, [currentMonth]);

  const prevMonth = () => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1));
  const nextMonth = () => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1));
  const goToday = () => setCurrentMonth(startOfMonth(new Date()));

  const monthLabel = currentMonth.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
  const today = new Date();

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Month navigation */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-[var(--text-primary)]">{monthLabel}</h3>
        <div className="flex items-center gap-2">
          <button onClick={goToday} className="px-2 py-1 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border)] rounded">
            Today
          </button>
          <button onClick={prevMonth} className="p-1 hover:bg-[var(--bg-secondary)] rounded text-[var(--text-secondary)]">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button onClick={nextMonth} className="p-1 hover:bg-[var(--bg-secondary)] rounded text-[var(--text-secondary)]">
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Day headers */}
      <div className="grid grid-cols-7 gap-px mb-px">
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
          <div key={day} className="px-2 py-1.5 text-xs font-medium text-[var(--text-secondary)] text-center uppercase tracking-wider">
            {day}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-px flex-1 overflow-y-auto bg-[var(--border)]">
        {calendarDays.map((date, idx) => {
          if (!date) {
            return <div key={`empty-${idx}`} className="bg-[var(--bg-primary)] min-h-[80px]" />;
          }

          const dayDeals = calendarDeals.filter(cd => isSameDay(cd.date, date));
          const isToday = isSameDay(date, today);

          return (
            <div
              key={date.toISOString()}
              className={`bg-[var(--bg-primary)] min-h-[80px] p-1.5 ${isToday ? 'ring-1 ring-inset ring-[var(--accent)]' : ''}`}
            >
              <div className={`text-xs mb-1 ${isToday ? 'text-[var(--accent)] font-bold' : 'text-[var(--text-secondary)]'}`}>
                {date.getDate()}
              </div>
              <div className="space-y-0.5">
                {dayDeals.slice(0, 3).map(({ deal, dateType }) => {
                  const stageConfig = getStageConfig(deal.stage);
                  return (
                    <div
                      key={`${deal.id}-${dateType}`}
                      className={`px-1.5 py-0.5 rounded text-[10px] truncate cursor-pointer hover:opacity-80 ${stageConfig.color} bg-opacity-20 text-[var(--text-primary)]`}
                      onClick={() => openDetailDrawer(deal.id)}
                      title={`${deal.name} — ${dateType === 'expected_close' ? 'Expected Close' : 'Lease Start'}: ${formatCurrency(deal.commission_amount)}`}
                    >
                      {deal.name}
                    </div>
                  );
                })}
                {dayDeals.length > 3 && (
                  <div className="text-[10px] text-[var(--text-secondary)] px-1">
                    +{dayDeals.length - 3} more
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-3 text-xs text-[var(--text-secondary)]">
        <span>Showing expected close dates and lease start dates</span>
        <span className="ml-auto font-mono">
          {calendarDeals.filter(cd => cd.date.getMonth() === currentMonth.getMonth() && cd.date.getFullYear() === currentMonth.getFullYear()).length} events this month
        </span>
      </div>
    </div>
  );
}
