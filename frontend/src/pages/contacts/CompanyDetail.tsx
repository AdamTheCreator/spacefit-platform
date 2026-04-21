import { useState } from 'react';
import { ArrowLeft, Send, Sun, Plus, Globe } from 'lucide-react';
import {
  companiesById, contactsForCompany, contactFullName,
  formatRelDays, formatSF,
} from './data';
import {
  CompanyLogo, ContactAvatar, VerifPill, ExpansionBadge,
  SectionHeader, AttrRow,
} from './ui';
import { EnrichDrawer } from './ContactDetail';

export function CompanyDetailPage({ companyId, onBack, onOpenContact, onToast }: {
  companyId: string;
  onBack: () => void;
  onOpenContact: (id: string) => void;
  onToast: (msg: string) => void;
}) {
  const [enrichOpen, setEnrichOpen] = useState(false);
  const co = companiesById[companyId];
  if (!co) return null;
  const cts = contactsForCompany(companyId);
  const verified = cts.filter(c => c.verif === 'verified').length;
  const stale = cts.filter(c => c.verif === 'stale' || c.verif === 'bounced').length;

  return (
    <div style={{ padding: '0 32px 80px', maxWidth: 1280, margin: '0 auto' }}>
      <button onClick={onBack}
        style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 13, padding: '8px 0', marginBottom: 10 }}>
        <ArrowLeft size={14} /> All companies
      </button>

      {/* Header card */}
      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start', padding: 24, background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', borderRadius: 16, marginBottom: 24 }}>
        <CompanyLogo company={co} size={72} radius={14} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <h1 className="font-display" style={{ fontSize: 28, letterSpacing: '-0.02em' }}>{co.name}</h1>
            <ExpansionBadge value={co.is_expanding} />
          </div>
          <div style={{ display: 'flex', gap: 16, fontSize: 13, color: 'var(--text-secondary)', flexWrap: 'wrap', marginBottom: 14 }}>
            <span>{co.sector}{co.subsector ? ` \u00B7 ${co.subsector}` : ''}</span>
            <span>&middot;</span>
            <a href={`https://${co.website}`} target="_blank" rel="noreferrer"
              style={{ color: 'var(--accent)', textDecoration: 'none', display: 'inline-flex', gap: 4, alignItems: 'center' }}>
              <Globe size={12} /> {co.website}
            </a>
            <span>&middot;</span>
            <span style={{ color: 'var(--text-muted)' }}>Last enriched {formatRelDays(co.enriched_days)}</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginTop: 6 }}>
            <Stat label="US locations" value={co.us_locations?.toLocaleString() || '\u2014'} />
            <Stat label="Typical SF" value={formatSF(co.sf_min, co.sf_max)} />
            <Stat label="Contacts" value={`${cts.length}`} sub={`${verified} verified${stale ? ` \u00B7 ${stale} stale` : ''}`} />
            <Stat label="Target markets" value={(co.target_markets || []).slice(0, 2).join(', ') || '\u2014'} sub={co.target_markets && co.target_markets.length > 2 ? `+${co.target_markets.length - 2} more` : undefined} />
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <button className="btn-industrial-primary text-xs px-3 py-2 rounded-lg flex items-center gap-1.5"
            onClick={() => onToast('Contacts added to Outreach draft')}>
            <Send size={14} /> Send to Outreach
          </button>
          <button className="btn-industrial-secondary text-xs px-3 py-2 rounded-lg flex items-center gap-1.5"
            onClick={() => setEnrichOpen(true)}>
            <Sun size={14} /> Enrich
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 24 }}>
        {/* Main: contacts table + notes */}
        <div>
          <SectionHeader title="People at this company" count={cts.length}
            action={
              <button className="text-xs px-2 py-1 rounded-md border border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] flex items-center gap-1"
                onClick={() => onToast('Add contact \u2014 opening form')}>
                <Plus size={14} /> Add contact
              </button>
            } />
          <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', borderRadius: 14, overflow: 'hidden', marginBottom: 28 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: 'var(--bg-tertiary)', borderBottom: '1px solid var(--border-default)' }}>
                  <th style={compactTh()}>Name</th>
                  <th style={compactTh()}>Role</th>
                  <th style={compactTh()}>Email</th>
                  <th style={compactTh(120)}>Status</th>
                  <th style={compactTh(130)}>Last contacted</th>
                </tr>
              </thead>
              <tbody>
                {cts.map(ct => (
                  <tr key={ct.id} onClick={() => onOpenContact(ct.id)}
                    className="hover:bg-[var(--bg-tertiary)] transition-colors"
                    style={{ borderBottom: '1px solid var(--border-default)', cursor: 'pointer' }}>
                    <td style={compactTd()}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <ContactAvatar contact={ct} size={28} />
                        <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{contactFullName(ct)}</span>
                      </div>
                    </td>
                    <td style={compactTd()}><span style={{ color: 'var(--text-secondary)' }}>{ct.role}</span></td>
                    <td style={compactTd()}>
                      {ct.email ? <span className="font-mono" style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{ct.email}</span>
                        : <span style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>&mdash;</span>}
                    </td>
                    <td style={compactTd()}><VerifPill status={ct.verif} sm /></td>
                    <td style={compactTd()}>
                      <span style={{ color: 'var(--text-muted)', fontSize: 12.5 }}>{formatRelDays(ct.last_contacted_days)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <SectionHeader title="Firm-wide notes" />
          <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', borderRadius: 14, padding: 18, marginBottom: 28 }}>
            {co.notes ? (
              <p style={{ fontSize: 13.5, color: 'var(--text-secondary)', lineHeight: 1.55, margin: 0 }}>{co.notes}</p>
            ) : (
              <p style={{ fontSize: 13, color: 'var(--text-muted)', fontStyle: 'italic', margin: 0 }}>No notes yet. Click to add a firm-wide note about this brand.</p>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div>
          <SectionHeader title="Brand profile" />
          <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', borderRadius: 14, padding: 18, marginBottom: 24 }}>
            <AttrRow label="Sector" value={co.sector} />
            {co.subsector && <AttrRow label="Subsector" value={co.subsector} />}
            <AttrRow label="Locations" value={`${co.us_locations?.toLocaleString() || '\u2014'} US`} />
            <AttrRow label="Typical SF" value={formatSF(co.sf_min, co.sf_max)} />
            <AttrRow label="Expansion" value={co.is_expanding === true ? 'Actively expanding' : co.is_expanding === false ? 'Not expanding' : 'Unknown'} />
            <AttrRow label="Target markets" value={(co.target_markets || []).join(', ') || '\u2014'} />
            <AttrRow label="Website" value={co.website} mono />
            <AttrRow label="Apollo ID" value={`apollo_${co.id.replace('co_', '')}`} mono dim last />
          </div>
        </div>
      </div>

      {enrichOpen && <EnrichDrawer entity={co} kind="company" onClose={() => setEnrichOpen(false)} onToast={onToast} />}
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', fontWeight: 600 }}>{label}</div>
      <div className="font-display" style={{ fontSize: 19, fontWeight: 600, color: 'var(--text-primary)', marginTop: 4 }}>{value}</div>
      {sub && <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function compactTh(width?: number): React.CSSProperties {
  return {
    padding: '9px 14px', textAlign: 'left' as const,
    fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)',
    textTransform: 'uppercase' as const, letterSpacing: '0.06em',
    width: width || 'auto',
  };
}

function compactTd(): React.CSSProperties {
  return { padding: '10px 14px' };
}
