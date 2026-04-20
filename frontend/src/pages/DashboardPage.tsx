import { useNavigate } from 'react-router-dom';
import { Plus, Search, FileText, Users, ArrowRight } from 'lucide-react';
import { AppLayout } from '../components/Layout/AppLayout';
import { LineChart } from '../components/Dashboard/MiniCharts';
import { useAuthStore } from '../stores/authStore';

function formatToday(): { eyebrow: string; title: string } {
  const now = new Date();
  const weekday = now.toLocaleDateString('en-US', { weekday: 'long' });
  const month = now.toLocaleDateString('en-US', { month: 'long' });
  const day = now.getDate();
  const hour = now.getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  return { eyebrow: `${weekday.toUpperCase()} · ${month.toUpperCase()} ${day}`, title: greeting };
}

function StatTile({
  label,
  value,
  delta,
  tone = 'up',
}: {
  label: string;
  value: string;
  delta?: string;
  tone?: 'up' | 'down' | 'flat';
}) {
  const deltaColor =
    tone === 'down' ? 'text-[var(--color-error)]'
    : tone === 'flat' ? 'text-industrial-secondary'
    : 'text-[var(--color-success)]';
  return (
    <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-5">
      <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-industrial-secondary">
        {label}
      </div>
      <div className="font-display font-semibold text-[28px] text-industrial mt-1.5 leading-none tracking-tight">
        {value}
      </div>
      {delta && <div className={`text-xs mt-1.5 font-medium ${deltaColor}`}>{delta}</div>}
    </div>
  );
}

type ActivityTone = 'mist' | 'gold' | 'orange' | 'navy' | 'green';
interface ActivityRow {
  who: string;
  act: string;
  what: string;
  detail: string;
  when: string;
  tone: ActivityTone;
}

const RECENT_ACTIVITY: ActivityRow[] = [
  { who: 'Sam Okafor', act: 'moved', what: 'Harper & Ninth', detail: 'LOI sent', when: '2h ago', tone: 'mist' },
  { who: 'You', act: 'underwrote', what: 'Elm Grove Apartments', detail: 'Core+ thesis · 92', when: '4h ago', tone: 'gold' },
  { who: 'Nia Chen', act: 'flagged', what: 'Cypress Yards', detail: 'comp drift +4.2%', when: 'Yesterday', tone: 'orange' },
  { who: 'Market pulse', act: 'alerted', what: 'Austin submarket', detail: 'cap rate trending up', when: 'Yesterday', tone: 'navy' },
  { who: 'Dmitri V.', act: 'closed', what: 'Riverbend Flats', detail: '$14.2M acquisition', when: '2d ago', tone: 'green' },
];

interface UpcomingItem {
  day: string;
  date: string;
  title: string;
  meta: string;
  highlight?: boolean;
}

const UPCOMING: UpcomingItem[] = [
  { day: 'TUE', date: '22', title: 'Diligence call · Harper & Ninth', meta: '10:30 AM · 4 attendees' },
  { day: 'WED', date: '23', title: 'Market pulse review', meta: '2:00 PM · Weekly' },
  { day: 'THU', date: '24', title: 'Close · Riverbend Flats', meta: 'Final signatures · $14.2M', highlight: true },
  { day: 'FRI', date: '25', title: 'LP quarterly report', meta: 'Draft due to Maya' },
];

function initials(name: string): string {
  return name.split(' ').map(n => n[0]).slice(0, 2).join('').toUpperCase();
}

export function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { eyebrow, title } = formatToday();
  const firstName = user?.first_name || 'there';

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="px-8 py-7 grid gap-5 max-w-[1400px]">
          {/* Welcome banner — space navy with starfield + Planner goose */}
          <div className="relative bg-[var(--color-neutral-900)] rounded-[20px] p-8 overflow-hidden text-white">
            {/* Starfield decoration */}
            <div className="absolute w-1 h-1 rounded-full bg-[#A7C7F7] opacity-70" style={{ top: 20, left: 30 }} />
            <div className="absolute w-1 h-1 rounded-full bg-[#E5B85C] opacity-80" style={{ top: 60, left: 90 }} />
            <div className="absolute w-[3px] h-[3px] rounded-full bg-[#A7C7F7] opacity-60" style={{ top: 130, left: 60 }} />
            <div className="absolute w-1 h-1 rounded-full bg-[#A7C7F7] opacity-70" style={{ top: 40, left: 260 }} />
            <div className="absolute w-[3px] h-[3px] rounded-full bg-[#A7C7F7] opacity-50" style={{ top: 90, right: 120 }} />
            <div className="absolute w-1 h-1 rounded-full bg-[#E5B85C] opacity-60" style={{ top: 30, right: 40 }} />

            <div className="relative flex gap-6 items-center flex-col sm:flex-row">
              <img
                src="/mascots/goose-planner.webp"
                alt=""
                aria-hidden="true"
                className="w-32 h-32 sm:w-[140px] sm:h-[140px] object-contain shrink-0 select-none"
                draggable={false}
              />
              <div className="flex-1 text-center sm:text-left">
                <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#E5B85C]">
                  {eyebrow}
                </div>
                <h2 className="font-display text-2xl sm:text-[28px] text-white mt-2 tracking-tight">
                  {title}, {firstName}.
                </h2>
                <p className="text-[14.5px] leading-[1.55] text-white/70 mt-2 max-w-[520px] mx-auto sm:mx-0">
                  3 new properties match your thesis overnight, the Harper &amp; Ninth deal is ready for review,
                  and your Q2 pipeline is trending 12% ahead.
                </p>
                <div className="flex gap-2.5 mt-4 justify-center sm:justify-start flex-wrap">
                  <button
                    onClick={() => navigate('/chat?context=matches')}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white font-semibold text-sm transition-colors shadow-sm"
                  >
                    Review new matches
                  </button>
                  <button
                    onClick={() => navigate('/pipeline')}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium text-white/90 hover:text-white hover:bg-white/10 transition-colors"
                  >
                    Open pipeline →
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Stat row */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatTile label="Active deals" value="14" delta="+2 this week" />
            <StatTile label="Pipeline value" value="$312M" delta="+12.4% vs. Q1" />
            <StatTile label="Avg underwriting time" value="1.8d" delta="−22% YoY" />
            <StatTile label="Thesis matches" value="27" delta="+3 overnight" />
          </div>

          {/* Chart + Quick actions */}
          <div className="grid grid-cols-1 lg:grid-cols-[1.6fr_1fr] gap-5">
            <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-6">
              <div className="flex justify-between items-start mb-4 flex-wrap gap-3">
                <div>
                  <h3 className="font-display text-base font-semibold text-industrial">Pipeline velocity</h3>
                  <div className="text-xs text-industrial-secondary mt-0.5">
                    Deals moving through stages · last 90 days
                  </div>
                </div>
                <div className="flex gap-1.5">
                  <span className="inline-flex items-center px-2.5 py-1 rounded-full bg-[var(--color-neutral-900)] text-white text-[11px] font-medium">
                    90d
                  </span>
                  <span className="inline-flex items-center px-2.5 py-1 rounded-full bg-[var(--bg-tertiary)] text-industrial-secondary text-[11px] font-medium">
                    30d
                  </span>
                  <span className="inline-flex items-center px-2.5 py-1 rounded-full bg-[var(--bg-tertiary)] text-industrial-secondary text-[11px] font-medium">
                    7d
                  </span>
                </div>
              </div>
              <LineChart
                data={[12, 14, 13, 16, 18, 17, 20, 19, 22, 24, 23, 26, 28, 30, 29, 32, 34, 33, 36, 38]}
                height={180}
              />
              <div className="grid grid-cols-4 gap-3 mt-5 pt-5 border-t border-[var(--border-subtle)]">
                {[
                  { label: 'Sourced', value: '84', accent: false },
                  { label: 'Screening', value: '32', accent: false },
                  { label: 'LOI', value: '14', accent: false },
                  { label: 'Closed', value: '6', accent: true },
                ].map(s => (
                  <div key={s.label}>
                    <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-industrial-secondary">
                      {s.label}
                    </div>
                    <div
                      className={`font-display font-semibold text-xl mt-0.5 ${
                        s.accent ? 'text-[var(--accent)]' : 'text-industrial'
                      }`}
                    >
                      {s.value}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Quick actions */}
            <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-6">
              <h3 className="font-display text-base font-semibold text-industrial mb-4">Quick actions</h3>
              <div className="grid gap-2.5">
                {[
                  { label: 'Add a property', icon: Plus, to: '/projects' },
                  { label: 'Run a comp search', icon: Search, to: '/chat?context=market_comps' },
                  { label: 'Start an underwrite', icon: FileText, to: '/chat' },
                  { label: 'Invite a teammate', icon: Users, to: '/settings' },
                ].map(a => {
                  const Icon = a.icon;
                  return (
                    <button
                      key={a.label}
                      onClick={() => navigate(a.to)}
                      className="flex items-center gap-3 px-3.5 py-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] hover:border-[var(--color-neutral-900)] hover:bg-[var(--bg-cream,var(--bg-tertiary))] cursor-pointer text-left w-full transition-colors group"
                    >
                      <div className="w-8 h-8 bg-[var(--bg-tertiary)] rounded-lg flex items-center justify-center text-[var(--color-orbit,#3A5BA0)] shrink-0">
                        <Icon size={16} />
                      </div>
                      <span className="text-sm font-medium text-industrial flex-1">{a.label}</span>
                      <ArrowRight size={14} className="text-industrial-muted group-hover:text-industrial transition-colors" />
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Recent activity + Upcoming */}
          <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-5 pb-8">
            <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl overflow-hidden">
              <div className="flex justify-between items-center px-6 py-5 border-b border-[var(--border-subtle)]">
                <h3 className="font-display text-base font-semibold text-industrial">Recent activity</h3>
                <button className="text-xs font-medium text-industrial-secondary hover:text-industrial transition-colors">
                  View all
                </button>
              </div>
              {RECENT_ACTIVITY.map((r, i) => (
                <div
                  key={i}
                  className={`flex gap-3.5 px-6 py-3.5 items-center ${
                    i < RECENT_ACTIVITY.length - 1 ? 'border-b border-[var(--border-subtle)]' : ''
                  }`}
                >
                  <div
                    className="w-8 h-8 rounded-full bg-gradient-to-br from-[var(--color-orbit,#3A5BA0)] to-[var(--color-mist,#A7C7F7)] text-white font-display font-semibold text-[11px] flex items-center justify-center shrink-0"
                    aria-hidden="true"
                  >
                    {initials(r.who)}
                  </div>
                  <div className="flex-1 text-[13.5px] text-industrial-secondary leading-[1.5] min-w-0">
                    <span className="font-semibold text-industrial">{r.who}</span>{' '}
                    {r.act} <span className="font-medium text-industrial">{r.what}</span>
                    <div className="text-xs text-industrial-secondary mt-0.5">{r.detail}</div>
                  </div>
                  <span className="text-xs text-industrial-muted shrink-0">{r.when}</span>
                </div>
              ))}
            </div>

            <div className="bg-[var(--bg-secondary)] border border-[var(--border-subtle)] rounded-xl p-6">
              <h3 className="font-display text-base font-semibold text-industrial mb-4">Upcoming</h3>
              {UPCOMING.map((u, i) => (
                <div
                  key={i}
                  className={`flex gap-3 py-3 items-center ${
                    i < UPCOMING.length - 1 ? 'border-b border-[var(--border-subtle)]' : ''
                  }`}
                >
                  <div
                    className={`w-[42px] rounded-lg py-1.5 text-center shrink-0 ${
                      u.highlight
                        ? 'bg-[var(--accent)] text-white'
                        : 'bg-[var(--bg-tertiary)] text-industrial'
                    }`}
                  >
                    <div className="text-[10px] font-semibold tracking-[0.08em]">{u.day}</div>
                    <div className="font-display font-bold text-base leading-tight">{u.date}</div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] font-semibold text-industrial truncate">{u.title}</div>
                    <div className="text-xs text-industrial-secondary mt-0.5">{u.meta}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

export default DashboardPage;
