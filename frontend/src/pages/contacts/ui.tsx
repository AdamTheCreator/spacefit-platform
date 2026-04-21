import { useState, useRef, useEffect, type ReactNode } from 'react';
import { Search, Check, X, ChevronDown, Sparkles, Sun } from 'lucide-react';
import type { Company, Contact, VerificationStatus } from './data';
import { sectorBg, contactInitials, verifLabel } from './data';

// ---- Company logo / monogram ----
export function CompanyLogo({ company, size = 36, radius = 8 }: { company: Company; size?: number; radius?: number }) {
  const bg = company.logo_bg || sectorBg(company.sector);
  const label = company.logo_text || (company.name || '?').slice(0, 2);
  const hex = bg.replace('#', '');
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);
  const lum = 0.299 * r + 0.587 * g + 0.114 * b;
  const fg = lum > 180 ? '#0F1B2D' : '#fff';
  return (
    <div style={{
      width: size, height: size, borderRadius: radius,
      background: bg, color: fg,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontWeight: 700, fontSize: size * 0.4, letterSpacing: '-0.02em',
      flexShrink: 0, border: '1px solid rgba(15,27,45,0.08)',
    }}>{label}</div>
  );
}

// ---- Contact avatar (initials) ----
export function ContactAvatar({ contact, size = 32 }: { contact: Contact; size?: number }) {
  const name = (contact.first || '') + ' ' + (contact.last || '');
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  const palette = ['#3A5BA0', '#FF8A3D', '#E5B85C', '#2F7A3B', '#8A6417', '#C25E1F', '#0F1B2D'];
  const bg = palette[h % palette.length];
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      background: bg, color: '#fff',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontWeight: 600, fontSize: size * 0.38, letterSpacing: '-0.01em',
      flexShrink: 0,
    }}>{contactInitials(contact)}</div>
  );
}

// ---- Verification pill ----
export function VerifPill({ status, sm }: { status: VerificationStatus; sm?: boolean }) {
  const v = verifLabel[status] || verifLabel.unverified;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: sm ? '2px 7px' : '3px 9px',
      borderRadius: 999, fontSize: sm ? 10.5 : 11.5, fontWeight: 500,
      background: v.bg, color: v.fg,
    }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: v.dot }} />
      {v.label}
    </span>
  );
}

// ---- Expansion indicator ----
export function ExpansionBadge({ value }: { value: boolean | null }) {
  if (value === true) return (
    <span className="pill pill-green" style={{ fontSize: 11, padding: '3px 9px', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#2F7A3B' }} />
      Expanding
    </span>
  );
  if (value === false) return (
    <span style={{ fontSize: 11, padding: '3px 9px', borderRadius: 999, background: '#F2F5F9', color: '#596779', display: 'inline-flex', alignItems: 'center' }}>
      Not expanding
    </span>
  );
  return (
    <span style={{ fontSize: 11, padding: '3px 9px', borderRadius: 999, background: '#F2F5F9', color: '#A7ADB7', display: 'inline-flex', alignItems: 'center' }}>
      &mdash;
    </span>
  );
}

// ---- Search input ----
export function SearchInput({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '8px 12px', borderRadius: 10,
      background: '#fff', border: '1px solid var(--border-default)',
      minWidth: 260, maxWidth: 360, flex: 1,
    }}>
      <Search size={15} className="text-[var(--text-muted)]" />
      <input value={value} onChange={e => onChange(e.target.value)}
        placeholder={placeholder || 'Search\u2026'}
        style={{ border: 'none', outline: 'none', flex: 1, fontSize: 13, color: 'var(--text-primary)', background: 'transparent' }} />
    </div>
  );
}

// ---- Filter chip (select-style dropdown) ----
interface FilterOption { value: string | boolean; label: string }

export function FilterChip({ label, value, options, onChange, allLabel }: {
  label: string;
  value: string | boolean | null;
  options: FilterOption[];
  onChange: (v: any) => void;
  allLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onDoc = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);
  const active = value !== null && value !== undefined && value !== 'all';
  const selected = options.find(o => o.value === value);
  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button onClick={() => setOpen(o => !o)}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '7px 12px', borderRadius: 999,
          background: active ? 'var(--text-primary)' : '#fff',
          color: active ? '#fff' : 'var(--text-primary)',
          border: `1px solid ${active ? 'var(--text-primary)' : 'var(--border-strong)'}`,
          fontSize: 12.5, fontWeight: 500, cursor: 'pointer', whiteSpace: 'nowrap',
        }}>
        <span style={{ color: active ? 'rgba(255,255,255,0.7)' : 'var(--text-muted)' }}>{label}</span>
        <span style={{ fontWeight: 600 }}>{selected ? selected.label : (allLabel || 'Any')}</span>
        <ChevronDown size={12} />
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 6px)', left: 0, zIndex: 40,
          background: '#fff', border: '1px solid var(--border-strong)',
          borderRadius: 10, boxShadow: 'var(--shadow-lg)', padding: 6, minWidth: 200,
        }}>
          {[{ value: 'all' as any, label: allLabel || 'Any' }, ...options].map(opt => (
            <button key={String(opt.value)} onClick={() => { onChange(opt.value === 'all' ? null : opt.value); setOpen(false); }}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                width: '100%', padding: '8px 10px', borderRadius: 6,
                background: (value === opt.value || (!value && opt.value === 'all')) ? 'var(--bg-tertiary)' : 'transparent',
                border: 'none', cursor: 'pointer', fontSize: 13, color: 'var(--text-primary)', textAlign: 'left',
              }}>
              {(value === opt.value || (!value && opt.value === 'all')) && <Check size={13} className="text-[var(--accent)]" />}
              <span style={{ marginLeft: (value === opt.value || (!value && opt.value === 'all')) ? 0 : 21 }}>{opt.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---- Selection action bar ----
export function SelectionBar({ count, kind, onClear, onSend, onEnrich }: {
  count: number; kind: string;
  onClear: () => void; onSend: () => void; onEnrich: () => void;
}) {
  if (count === 0) return null;
  return (
    <div style={{
      position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)', zIndex: 100,
      background: 'var(--text-primary)', color: '#fff',
      borderRadius: 14, padding: '10px 14px', boxShadow: 'var(--shadow-lg)',
      display: 'flex', alignItems: 'center', gap: 14, minWidth: 480,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{
          fontSize: 13, fontWeight: 600, padding: '4px 10px', borderRadius: 999,
          background: 'var(--accent)', color: '#fff',
        }}>{count}</span>
        <span style={{ fontSize: 13.5 }}>{count === 1 ? `${kind} selected` : `${kind}s selected`}</span>
      </div>
      <div style={{ flex: 1 }} />
      <button onClick={onEnrich}
        style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 12px', background: 'transparent', color: '#fff', border: '1px solid rgba(255,255,255,0.25)', borderRadius: 8, fontSize: 13, cursor: 'pointer' }}>
        <Sun size={14} /> Enrich
      </button>
      <button onClick={onSend}
        style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
        Send to Outreach
      </button>
      <button onClick={onClear} aria-label="Clear selection"
        style={{ padding: 6, background: 'transparent', color: 'rgba(255,255,255,0.6)', border: 'none', cursor: 'pointer', display: 'flex' }}>
        <X size={16} />
      </button>
    </div>
  );
}

// ---- Toast ----
export function Toast({ msg, onClose }: { msg: string | null; onClose: () => void }) {
  useEffect(() => { if (msg) { const t = setTimeout(onClose, 2400); return () => clearTimeout(t); } }, [msg, onClose]);
  if (!msg) return null;
  return (
    <div style={{
      position: 'fixed', bottom: 24, right: 24, zIndex: 200,
      background: 'var(--text-primary)', color: '#fff',
      padding: '10px 16px', borderRadius: 10, fontSize: 13,
      boxShadow: 'var(--shadow-lg)',
    }}>{msg}</div>
  );
}

// ---- Section header ----
export function SectionHeader({ title, count, action }: { title: string; count?: number; action?: ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
      <h3 style={{ fontSize: 11.5, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>{title}</h3>
      {count !== undefined && <span style={{ fontSize: 11, padding: '1px 7px', borderRadius: 999, background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>{count}</span>}
      <div style={{ flex: 1 }} />
      {action}
    </div>
  );
}

// ---- Attribute row (key-value for detail sidebars) ----
export function AttrRow({ label, value, mono, dim, last }: { label: string; value: ReactNode; mono?: boolean; dim?: boolean; last?: boolean }) {
  return (
    <div style={{ display: 'flex', padding: '9px 0', borderBottom: last ? 'none' : '1px solid var(--border-default)', alignItems: 'center', gap: 12 }}>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', width: 120, flexShrink: 0 }}>{label}</div>
      <div className={mono ? 'font-mono' : ''} style={{ fontSize: mono ? 12.5 : 13, color: dim ? 'var(--text-muted)' : 'var(--text-primary)', wordBreak: 'break-word', minWidth: 0, flex: 1 }}>
        {value}
      </div>
    </div>
  );
}

// ---- Table header/cell style helpers ----
export function thStyle(width?: number): React.CSSProperties {
  return {
    padding: '10px 14px', textAlign: 'left' as const,
    fontSize: 11.5, fontWeight: 600, color: 'var(--text-secondary)',
    textTransform: 'uppercase' as const, letterSpacing: '0.06em',
    width: width || 'auto',
  };
}

export function tdStyle(): React.CSSProperties {
  return { padding: '12px 14px', verticalAlign: 'middle' as const };
}
