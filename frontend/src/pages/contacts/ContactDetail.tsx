import { useState, useMemo } from 'react';
import {
  ArrowLeft, Send, Calendar, Sun, X, Check, ChevronRight,
  Mail, Phone, Sparkles, FileText,
} from 'lucide-react';
import type { Company, Contact, Interaction, InteractionType } from './data';
import {
  contactsById, companiesById, interactions,
  contactFullName, formatRelDays, sourceLabel,
} from './data';
import {
  ContactAvatar, CompanyLogo, VerifPill, SectionHeader, AttrRow,
} from './ui';

// ---- Contact detail page ----
export function ContactDetailPage({ contactId, onBack, onOpenCompany, onToast }: {
  contactId: string;
  onBack: () => void;
  onOpenCompany: (id: string) => void;
  onToast: (msg: string) => void;
}) {
  const ct = contactsById[contactId];
  if (!ct) return null;
  const co = companiesById[ct.company_id];
  const [tab, setTab] = useState('history');
  const [enrichOpen, setEnrichOpen] = useState(false);
  const [noteDraft, setNoteDraft] = useState('');
  const [meetingOpen, setMeetingOpen] = useState(false);
  const [extraEvents, setExtraEvents] = useState<TimelineEvent[]>([]);

  const events = useMemo(() => buildTimeline(ct, extraEvents), [ct, extraEvents]);
  const stale = ct.verif === 'stale' || ct.verif === 'bounced';

  return (
    <div style={{ padding: '0 32px 80px', maxWidth: 1180, margin: '0 auto' }}>
      <button onClick={onBack}
        style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 13, padding: '8px 0', marginBottom: 10 }}>
        <ArrowLeft size={14} /> All contacts
      </button>

      {stale && (
        <div style={{
          padding: '12px 16px', borderRadius: 12, marginBottom: 16,
          background: ct.verif === 'bounced' ? '#FCE3DA' : '#FBEFC8',
          border: ct.verif === 'bounced' ? '1px solid #F1B89C' : '1px solid #F3DFA6',
          display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <div style={{ flex: 1, fontSize: 13, color: ct.verif === 'bounced' ? '#7A361A' : '#8A6417' }}>
            <strong>{ct.verif === 'bounced' ? 'Email bounced on last send.' : 'This contact may be stale.'}</strong>
            {' '}Last verified {formatRelDays(ct.last_verified_days)}. {ct.notes}
          </div>
          <button className="btn-industrial-secondary text-xs px-3 py-1.5 rounded-lg" onClick={() => setEnrichOpen(true)}>Re-enrich</button>
          <button className="text-xs px-3 py-1.5 rounded-lg border border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
            onClick={() => onToast('Marked verified')}>Mark verified</button>
        </div>
      )}

      {/* Header card */}
      <div style={{ display: 'flex', gap: 22, alignItems: 'flex-start', padding: 24, background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', borderRadius: 16, marginBottom: 24 }}>
        <ContactAvatar contact={ct} size={72} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <h1 className="font-display" style={{ fontSize: 26, letterSpacing: '-0.02em' }}>{contactFullName(ct)}</h1>
            <VerifPill status={ct.verif} />
          </div>
          <div style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 14 }}>
            {ct.role} at{' '}
            <button onClick={() => onOpenCompany(co.id)}
              style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', color: 'var(--text-primary)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 14 }}>
              <CompanyLogo company={co} size={20} radius={5} /> {co?.name}
            </button>
          </div>
          <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', fontSize: 13 }}>
            {ct.email && <InfoPiece icon={<Mail size={13} />} value={ct.email} mono />}
            {ct.phone && <InfoPiece icon={<Phone size={13} />} value={ct.phone} />}
            {ct.linkedin && <InfoPiece icon={<span style={{ fontSize: 10 }}>in</span>} value="LinkedIn profile" link />}
            <InfoPiece icon={<Sparkles size={13} />} value={`Source: ${sourceLabel(ct.source)}`} dim />
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <button className="btn-industrial-primary text-xs px-3 py-2 rounded-lg flex items-center gap-1.5"
            onClick={() => onToast('Thread drafted \u2014 opening Outreach')}>
            <Send size={14} /> Send email
          </button>
          <button className="btn-industrial-secondary text-xs px-3 py-2 rounded-lg flex items-center gap-1.5"
            onClick={() => setMeetingOpen(true)}>
            <Calendar size={14} /> Log meeting
          </button>
          <button className="btn-industrial-secondary text-xs px-3 py-2 rounded-lg flex items-center gap-1.5"
            onClick={() => setEnrichOpen(true)}>
            <Sun size={14} /> Enrich
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 24 }}>
        <div>
          {/* Add-note inline */}
          <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', borderRadius: 14, padding: 16, marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
              <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--accent)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 600, flexShrink: 0 }}>AB</div>
              <div style={{ flex: 1 }}>
                <textarea value={noteDraft} onChange={e => setNoteDraft(e.target.value)}
                  placeholder={`Add a note about ${ct.first}\u2026`}
                  style={{ width: '100%', minHeight: 40, border: 'none', outline: 'none', fontSize: 13.5, color: 'var(--text-primary)', resize: 'vertical', padding: 0, background: 'transparent' }} />
                {noteDraft.trim() && (
                  <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                    <button className="btn-industrial-primary text-xs px-3 py-1.5 rounded-lg" onClick={() => {
                      setExtraEvents(e => [{ id: `new_${Date.now()}`, type: 'note', when_days: 0, who: 'Adam Barlow', summary: noteDraft }, ...e]);
                      setNoteDraft('');
                      onToast('Note added');
                    }}>Add note</button>
                    <button className="text-xs px-3 py-1.5 rounded-lg border border-[var(--border-default)] text-[var(--text-secondary)]"
                      onClick={() => setNoteDraft('')}>Cancel</button>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* History tabs */}
          <div style={{ display: 'flex', gap: 4, marginBottom: 14, borderBottom: '1px solid var(--border-default)' }}>
            {([['history', 'Interaction history'], ['notes', 'Notes only']] as const).map(([id, label]) => (
              <button key={id} onClick={() => setTab(id)}
                style={{ padding: '8px 12px', border: 'none', background: 'transparent', cursor: 'pointer', fontSize: 13, fontWeight: tab === id ? 600 : 500, color: tab === id ? 'var(--text-primary)' : 'var(--text-secondary)', borderBottom: `2px solid ${tab === id ? 'var(--accent)' : 'transparent'}`, marginBottom: -1 }}>
                {label}
              </button>
            ))}
          </div>

          <Timeline events={tab === 'notes' ? events.filter(e => e.type === 'note') : events} />
        </div>

        {/* Sidebar */}
        <div>
          <SectionHeader title="Details" />
          <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', borderRadius: 14, padding: 18, marginBottom: 24 }}>
            <AttrRow label="Role" value={ct.role} />
            <AttrRow label="Email" value={ct.email || '\u2014'} mono={!!ct.email} />
            <AttrRow label="Phone" value={ct.phone || '\u2014'} />
            <AttrRow label="Status" value={<VerifPill status={ct.verif} sm />} />
            <AttrRow label="Last verified" value={formatRelDays(ct.last_verified_days)} />
            <AttrRow label="Last contacted" value={formatRelDays(ct.last_contacted_days)} />
            <AttrRow label="Last reply" value={formatRelDays(ct.last_reply_days)} />
            <AttrRow label="Source" value={sourceLabel(ct.source)} last />
          </div>

          {ct.notes && (
            <>
              <SectionHeader title="About this person" />
              <div style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-default)', borderRadius: 14, padding: 16, marginBottom: 24, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.55 }}>
                {ct.notes}
              </div>
            </>
          )}
        </div>
      </div>

      {enrichOpen && <EnrichDrawer entity={ct} kind="contact" onClose={() => setEnrichOpen(false)} onToast={onToast} />}
      {meetingOpen && <LogMeetingModal onClose={() => setMeetingOpen(false)} onSave={(m) => {
        setExtraEvents(e => [{ id: `mt_${Date.now()}`, type: 'meeting', when_days: 0, who: 'Adam Barlow', title: m.title, summary: m.summary }, ...e]);
        setMeetingOpen(false);
        onToast('Meeting logged');
      }} />}
    </div>
  );
}

// ---- Timeline ----
interface TimelineEvent {
  id: string;
  type: InteractionType;
  when_days: number;
  who: string;
  title?: string;
  summary: string;
}

function buildTimeline(ct: Contact, extra: TimelineEvent[]): TimelineEvent[] {
  const events: TimelineEvent[] = [...extra];
  interactions.filter(i => i.contact_id === ct.id).forEach(i => events.push({ ...i }));
  events.sort((a, b) => (a.when_days ?? 999) - (b.when_days ?? 999));
  return events;
}

function eventIcon(t: InteractionType) {
  switch (t) {
    case 'email_in': return <Mail size={14} />;
    case 'email_out': return <Send size={14} />;
    case 'meeting': return <Calendar size={14} />;
    case 'enrich': return <Sun size={14} />;
    default: return <FileText size={14} />;
  }
}

function eventColor(t: InteractionType): string {
  return ({ email_in: '#2F7A3B', email_out: 'var(--accent)', meeting: '#FF8A3D', note: 'var(--text-muted)', enrich: '#8A6417' })[t] || 'var(--text-muted)';
}

function eventTitle(ev: TimelineEvent): string {
  return ({ email_in: 'Reply received', email_out: 'Email sent', meeting: 'Meeting logged', note: 'Note', enrich: 'Enrichment' })[ev.type] || 'Event';
}

function Timeline({ events }: { events: TimelineEvent[] }) {
  if (!events || events.length === 0) {
    return (
      <div style={{ background: 'var(--bg-secondary)', border: '1px dashed var(--border-strong)', borderRadius: 14, padding: '40px 20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
        No interactions yet. Send an email or log a meeting to start the history.
      </div>
    );
  }
  return (
    <div style={{ position: 'relative' }}>
      <div style={{ position: 'absolute', left: 15, top: 12, bottom: 12, width: 1, background: 'var(--border-default)' }} />
      {events.map(ev => (
        <div key={ev.id} style={{ display: 'flex', gap: 14, marginBottom: 14, position: 'relative' }}>
          <div style={{
            width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
            background: 'var(--bg-secondary)', border: '1px solid var(--border-default)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: eventColor(ev.type), zIndex: 1,
          }}>
            {eventIcon(ev.type)}
          </div>
          <div style={{ flex: 1, background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', borderRadius: 12, padding: '12px 14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{eventTitle(ev)}</span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>&middot; {ev.who}</span>
              <span style={{ flex: 1 }} />
              <span style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>{formatRelDays(ev.when_days)}</span>
            </div>
            {ev.title && ev.type !== 'note' && (
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', fontWeight: 500, marginBottom: 4 }}>{ev.title}</div>
            )}
            {ev.summary && (
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>{ev.summary}</div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---- Enrich drawer ----
export function EnrichDrawer({ entity, kind, onClose, onToast }: {
  entity: Company | Contact;
  kind: 'company' | 'contact';
  onClose: () => void;
  onToast: (msg: string) => void;
}) {
  const proposals = kind === 'company' ? [
    { field: 'us_locations', label: 'US locations', current: String((entity as Company).us_locations), proposed: String((entity as Company).us_locations + 8), source: 'Apollo' },
    { field: 'typical_sf_max', label: 'Typical SF max', current: String((entity as Company).sf_max), proposed: String((entity as Company).sf_max + 200), source: 'Apollo' },
    { field: 'target_markets', label: 'Target markets', current: ((entity as Company).target_markets || []).join(', '), proposed: [...((entity as Company).target_markets || []), 'Boston'].join(', '), source: 'Apollo' },
  ] : [
    { field: 'role', label: 'Role', current: (entity as Contact).role, proposed: (entity as Contact).role.replace('Manager', 'Sr. Manager'), source: 'LinkedIn' },
    { field: 'phone', label: 'Direct phone', current: (entity as Contact).phone || '\u2014', proposed: (entity as Contact).phone || '(212) 555-0177', source: 'Apollo' },
    { field: 'verif', label: 'Email deliverability', current: (entity as Contact).verif, proposed: 'verified', source: 'ZeroBounce' },
  ];

  const [decisions, setDecisions] = useState<Record<string, string>>(() =>
    Object.fromEntries(proposals.map(p => [p.field, 'pending']))
  );
  const accepted = Object.values(decisions).filter(v => v === 'accepted').length;
  const rejected = Object.values(decisions).filter(v => v === 'rejected').length;
  const pending = Object.values(decisions).filter(v => v === 'pending').length;

  const displayName = kind === 'company' ? (entity as Company).name : contactFullName(entity as Contact);

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(15,27,45,0.35)', zIndex: 200, display: 'flex', justifyContent: 'flex-end' }} onClick={onClose}>
      <div onClick={e => e.stopPropagation()} style={{ width: 480, height: '100%', background: 'var(--bg-primary)', display: 'flex', flexDirection: 'column', boxShadow: 'var(--shadow-xl)' }}>
        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-default)', background: 'var(--bg-secondary)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 36, height: 36, borderRadius: 10, background: '#FBEFC8', color: '#8A6417', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Sun size={18} />
          </div>
          <div style={{ flex: 1 }}>
            <div className="font-display" style={{ fontSize: 16, color: 'var(--text-primary)' }}>Enrich {displayName}</div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>{proposals.length} proposed changes &middot; Review each before applying</div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 6, color: 'var(--text-muted)' }}>
            <X size={18} />
          </button>
        </div>

        <div style={{ flex: 1, overflow: 'auto', padding: '16px 20px' }}>
          {proposals.map(p => {
            const d = decisions[p.field];
            return (
              <div key={p.field} style={{
                background: 'var(--bg-secondary)',
                border: `1px solid ${d === 'accepted' ? '#BBD8C4' : d === 'rejected' ? 'var(--border-default)' : 'var(--border-strong)'}`,
                borderLeft: `3px solid ${d === 'accepted' ? '#2F7A3B' : d === 'rejected' ? 'var(--text-muted)' : 'var(--accent)'}`,
                borderRadius: 10, padding: 14, marginBottom: 12,
                opacity: d === 'rejected' ? 0.6 : 1,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-primary)' }}>{p.label}</span>
                  <span style={{ fontSize: 10.5, padding: '1px 7px', borderRadius: 999, background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>via {p.source}</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 10, alignItems: 'center', marginBottom: 12 }}>
                  <div>
                    <div style={{ fontSize: 10.5, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 2 }}>Current</div>
                    <div style={{ fontSize: 13, color: 'var(--text-secondary)', textDecoration: p.current === p.proposed ? 'none' : 'line-through' }}>{p.current || '\u2014'}</div>
                  </div>
                  <ChevronRight size={12} className="text-[var(--text-muted)]" />
                  <div>
                    <div style={{ fontSize: 10.5, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 2, fontWeight: 600 }}>Proposed</div>
                    <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 }}>{p.proposed}</div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => setDecisions(dc => ({ ...dc, [p.field]: 'accepted' }))}
                    style={{
                      flex: 1, padding: '7px 10px', borderRadius: 8, cursor: 'pointer',
                      border: `1px solid ${d === 'accepted' ? '#2F7A3B' : 'var(--border-strong)'}`,
                      background: d === 'accepted' ? '#E3F1E5' : 'var(--bg-secondary)',
                      color: d === 'accepted' ? '#2F7A3B' : 'var(--text-secondary)',
                      fontSize: 12.5, fontWeight: d === 'accepted' ? 600 : 500,
                      display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                    }}>
                    <Check size={13} /> Accept
                  </button>
                  <button onClick={() => setDecisions(dc => ({ ...dc, [p.field]: 'rejected' }))}
                    style={{
                      flex: 1, padding: '7px 10px', borderRadius: 8, cursor: 'pointer',
                      border: `1px solid ${d === 'rejected' ? 'var(--text-muted)' : 'var(--border-strong)'}`,
                      background: 'var(--bg-secondary)',
                      color: d === 'rejected' ? 'var(--text-secondary)' : 'var(--text-muted)',
                      fontSize: 12.5, fontWeight: d === 'rejected' ? 600 : 500,
                      display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                    }}>
                    <X size={13} /> Reject
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        <div style={{ padding: '14px 20px', borderTop: '1px solid var(--border-default)', background: 'var(--bg-secondary)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', flex: 1 }}>
            <strong style={{ color: '#2F7A3B' }}>{accepted}</strong> accepted &middot;{' '}
            <strong>{rejected}</strong> rejected &middot;{' '}
            <strong style={{ color: 'var(--accent)' }}>{pending}</strong> pending
          </div>
          <button className="text-xs px-3 py-1.5 rounded-lg border border-[var(--border-default)] text-[var(--text-secondary)]" onClick={onClose}>Cancel</button>
          <button className="btn-industrial-primary text-xs px-3 py-1.5 rounded-lg" onClick={() => { onToast(`${accepted} change${accepted === 1 ? '' : 's'} applied`); onClose(); }}>
            Apply {accepted || 0} change{accepted === 1 ? '' : 's'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---- Log meeting modal ----
function LogMeetingModal({ onClose, onSave }: {
  onClose: () => void;
  onSave: (m: { title: string; summary: string }) => void;
}) {
  const [title, setTitle] = useState('');
  const [summary, setSummary] = useState('');
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(15,27,45,0.4)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={onClose}>
      <div onClick={e => e.stopPropagation()} style={{ width: 520, background: 'var(--bg-secondary)', borderRadius: 14, padding: 24, boxShadow: 'var(--shadow-xl)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: '#FFF0E2', color: '#FF8A3D', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Calendar size={16} />
          </div>
          <h3 className="font-display" style={{ fontSize: 17 }}>Log a meeting</h3>
        </div>
        <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6, fontWeight: 500 }}>Title</label>
        <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Intro call, site tour, LOI walkthrough\u2026"
          className="w-full text-sm px-3 py-2 rounded-lg border border-[var(--border-default)] bg-[var(--bg-secondary)] outline-none focus:border-[var(--accent)] mb-3.5" />
        <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6, fontWeight: 500 }}>Summary</label>
        <textarea value={summary} onChange={e => setSummary(e.target.value)}
          placeholder="What was discussed? Next steps?"
          className="w-full text-sm px-3 py-2 rounded-lg border border-[var(--border-default)] bg-[var(--bg-secondary)] outline-none focus:border-[var(--accent)] mb-4"
          style={{ minHeight: 120, resize: 'vertical' }} />
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button className="text-xs px-3 py-1.5 rounded-lg border border-[var(--border-default)] text-[var(--text-secondary)]" onClick={onClose}>Cancel</button>
          <button className="btn-industrial-primary text-xs px-3 py-1.5 rounded-lg" disabled={!title.trim()}
            onClick={() => onSave({ title, summary })}>Log meeting</button>
        </div>
      </div>
    </div>
  );
}

// ---- Info piece (for contact header) ----
function InfoPiece({ icon, value, mono, dim, link }: { icon: React.ReactNode; value: string; mono?: boolean; dim?: boolean; link?: boolean }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: dim ? 'var(--text-muted)' : 'var(--text-secondary)' }}>
      <span style={{ color: dim ? 'var(--text-muted)' : 'var(--accent)' }}>{icon}</span>
      <span className={mono ? 'font-mono' : ''} style={{ fontSize: mono ? 12.5 : 13, color: link ? 'var(--accent)' : 'inherit', textDecoration: link ? 'underline' : 'none' }}>{value}</span>
    </span>
  );
}
