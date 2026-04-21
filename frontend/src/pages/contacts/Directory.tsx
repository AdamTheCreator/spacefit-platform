import { useState, useMemo } from 'react';
import { Sparkles } from 'lucide-react';
import {
  companies, contacts, companiesById, contactsForCompany,
  contactFullName, formatRelDays, formatSF,
} from './data';
import {
  CompanyLogo, ContactAvatar, VerifPill, ExpansionBadge,
  SearchInput, FilterChip, SelectionBar, thStyle, tdStyle,
} from './ui';

// ---- Tabs ----
function Tabs({ tab, setTab, counts }: {
  tab: string; setTab: (t: string) => void;
  counts: { companies: number; contacts: number; stale: number };
}) {
  const items = [
    { id: 'companies', label: 'Companies', count: counts.companies },
    { id: 'contacts', label: 'Contacts', count: counts.contacts },
    { id: 'stale', label: 'Needs attention', count: counts.stale, pill: true },
  ];
  return (
    <div style={{ display: 'flex', gap: 2, borderBottom: '1px solid var(--border-default)', marginBottom: 18 }}>
      {items.map(it => (
        <button key={it.id} onClick={() => setTab(it.id)}
          style={{
            padding: '10px 14px', border: 'none', background: 'transparent',
            cursor: 'pointer', fontSize: 13.5,
            fontWeight: tab === it.id ? 600 : 500,
            color: tab === it.id ? 'var(--text-primary)' : 'var(--text-secondary)',
            borderBottom: `2px solid ${tab === it.id ? 'var(--accent)' : 'transparent'}`,
            marginBottom: -1, display: 'flex', alignItems: 'center', gap: 8,
          }}>
          {it.label}
          <span style={{
            fontSize: 11, padding: '1px 7px', borderRadius: 999,
            background: it.pill && it.count > 0 ? '#FCE3DA' : 'var(--bg-tertiary)',
            color: it.pill && it.count > 0 ? '#C25E1F' : 'var(--text-secondary)',
            fontWeight: 500,
          }}>{it.count}</span>
        </button>
      ))}
    </div>
  );
}

// ---- Companies table ----
function CompaniesTable({ onOpenCompany, onToast }: {
  onOpenCompany: (id: string) => void; onToast: (msg: string) => void;
}) {
  const [q, setQ] = useState('');
  const [sector, setSector] = useState<string | null>(null);
  const [expanding, setExpanding] = useState<boolean | null>(null);
  const [market, setMarket] = useState<string | null>(null);
  const [sfBucket, setSfBucket] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const sectors = useMemo(() => [...new Set(companies.map(c => c.sector))].map(s => ({ value: s, label: s })), []);
  const markets = useMemo(() => {
    const all = new Set<string>();
    companies.forEach(c => (c.target_markets || []).forEach(m => all.add(m)));
    return [...all].sort().map(m => ({ value: m, label: m }));
  }, []);

  const filtered = useMemo(() => {
    return companies.filter(c => {
      if (q && !c.name.toLowerCase().includes(q.toLowerCase())) return false;
      if (sector && c.sector !== sector) return false;
      if (expanding !== null && c.is_expanding !== expanding) return false;
      if (market && !(c.target_markets || []).includes(market)) return false;
      if (sfBucket) {
        const mid = ((c.sf_min || 0) + (c.sf_max || 0)) / 2;
        if (sfBucket === 'sm' && mid >= 2000) return false;
        if (sfBucket === 'md' && (mid < 2000 || mid >= 3500)) return false;
        if (sfBucket === 'lg' && mid < 3500) return false;
      }
      return true;
    });
  }, [q, sector, expanding, market, sfBucket]);

  const toggleSel = (id: string) => setSelected(s => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const allSelected = filtered.length > 0 && filtered.every(c => selected.has(c.id));
  const toggleAll = () => {
    if (allSelected) setSelected(new Set());
    else setSelected(new Set(filtered.map(c => c.id)));
  };

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
        <SearchInput value={q} onChange={setQ} placeholder="Search companies\u2026" />
        <FilterChip label="Sector" value={sector} onChange={setSector} options={sectors} allLabel="All sectors" />
        <FilterChip label="Expanding" value={expanding} onChange={setExpanding}
          options={[{ value: true, label: 'Yes' }, { value: false, label: 'No' }]} allLabel="Any" />
        <FilterChip label="Market" value={market} onChange={setMarket} options={markets} allLabel="All markets" />
        <FilterChip label="Size" value={sfBucket} onChange={setSfBucket}
          options={[{ value: 'sm', label: '< 2K sf' }, { value: 'md', label: '2\u20133.5K sf' }, { value: 'lg', label: '3.5K+ sf' }]}
          allLabel="Any size" />
        <div style={{ marginLeft: 'auto', fontSize: 12.5, color: 'var(--text-secondary)' }}>
          {filtered.length} of {companies.length}
        </div>
      </div>

      <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', borderRadius: 14, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: 'var(--bg-tertiary)', borderBottom: '1px solid var(--border-default)' }}>
              <th style={thStyle(48)}>
                <input type="checkbox" checked={allSelected} onChange={toggleAll} style={{ cursor: 'pointer' }} />
              </th>
              <th style={thStyle()}>Brand</th>
              <th style={thStyle(160)}>Sector</th>
              <th style={thStyle(120)}>Locations</th>
              <th style={thStyle(130)}>Typical SF</th>
              <th style={thStyle(140)}>Expanding</th>
              <th style={thStyle(130)}>Contacts</th>
              <th style={thStyle(120)}>Last activity</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(c => {
              const cts = contactsForCompany(c.id);
              const verifCount = cts.filter(x => x.verif === 'verified').length;
              const staleCount = cts.filter(x => x.verif === 'stale' || x.verif === 'bounced').length;
              const lastContacted = Math.min(...cts.map(x => x.last_contacted_days ?? 9999));
              return (
                <tr key={c.id} onClick={() => onOpenCompany(c.id)}
                  className="hover:bg-[var(--bg-tertiary)] transition-colors"
                  style={{ borderBottom: '1px solid var(--border-default)', cursor: 'pointer' }}>
                  <td style={tdStyle()} onClick={e => e.stopPropagation()}>
                    <input type="checkbox" checked={selected.has(c.id)} onChange={() => toggleSel(c.id)} style={{ cursor: 'pointer' }} />
                  </td>
                  <td style={tdStyle()}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <CompanyLogo company={c} size={36} />
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 13.5 }}>{c.name}</div>
                        <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 1 }}>{c.website}</div>
                      </div>
                    </div>
                  </td>
                  <td style={tdStyle()}>
                    <div style={{ color: 'var(--text-secondary)' }}>{c.sector}</div>
                    {c.subsector && <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>{c.subsector}</div>}
                  </td>
                  <td style={tdStyle()}>
                    <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{c.us_locations?.toLocaleString() || '\u2014'}</span>
                    <span style={{ color: 'var(--text-muted)', fontSize: 11.5, marginLeft: 4 }}>US</span>
                  </td>
                  <td style={tdStyle()}>
                    <span style={{ color: 'var(--text-secondary)' }}>{formatSF(c.sf_min, c.sf_max)}</span>
                  </td>
                  <td style={tdStyle()}>
                    <ExpansionBadge value={c.is_expanding} />
                  </td>
                  <td style={tdStyle()}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{cts.length}</span>
                      <span style={{ color: 'var(--text-muted)', fontSize: 11.5 }}>&middot; {verifCount} verified</span>
                      {staleCount > 0 && (
                        <span style={{ color: '#C25E1F', fontSize: 11, fontWeight: 500 }}>&middot; {staleCount} stale</span>
                      )}
                    </div>
                  </td>
                  <td style={tdStyle()}>
                    <span style={{ color: lastContacted < 30 ? 'var(--text-primary)' : 'var(--text-muted)', fontSize: 12.5 }}>
                      {formatRelDays(lastContacted === 9999 ? null : lastContacted)}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <SelectionBar count={selected.size} kind="company"
        onClear={() => setSelected(new Set())}
        onSend={() => { onToast(`${selected.size} companies \u2014 send to Outreach campaign`); setSelected(new Set()); }}
        onEnrich={() => { onToast(`Enrichment queued for ${selected.size} companies`); setSelected(new Set()); }} />
    </div>
  );
}

// ---- Contacts table ----
function ContactsTable({ onOpenContact, onOpenCompany, onToast, staleOnly = false }: {
  onOpenContact: (id: string) => void;
  onOpenCompany: (id: string) => void;
  onToast: (msg: string) => void;
  staleOnly?: boolean;
}) {
  const [q, setQ] = useState('');
  const [sector, setSector] = useState<string | null>(null);
  const [verif, setVerif] = useState<string | null>(staleOnly ? 'attention' : null);
  const [hasEmail, setHasEmail] = useState<boolean | null>(null);
  const [recency, setRecency] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const sectors = useMemo(() => [...new Set(companies.map(c => c.sector))].map(s => ({ value: s, label: s })), []);

  const filtered = useMemo(() => {
    return contacts.filter(ct => {
      const co = companiesById[ct.company_id];
      if (q) {
        const hay = `${ct.first} ${ct.last} ${ct.role} ${co?.name || ''}`.toLowerCase();
        if (!hay.includes(q.toLowerCase())) return false;
      }
      if (sector && co?.sector !== sector) return false;
      if (verif === 'attention') {
        if (ct.verif !== 'stale' && ct.verif !== 'bounced') return false;
      } else if (verif && ct.verif !== verif) return false;
      if (hasEmail === true && !ct.email) return false;
      if (hasEmail === false && ct.email) return false;
      if (recency) {
        const d = ct.last_contacted_days;
        if (recency === 'week' && (d === null || d > 7)) return false;
        if (recency === 'month' && (d === null || d > 30)) return false;
        if (recency === 'never' && d !== null) return false;
      }
      return true;
    });
  }, [q, sector, verif, hasEmail, recency]);

  const toggleSel = (id: string) => setSelected(s => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const allSelected = filtered.length > 0 && filtered.every(c => selected.has(c.id));
  const toggleAll = () => {
    if (allSelected) setSelected(new Set());
    else setSelected(new Set(filtered.map(c => c.id)));
  };

  return (
    <div>
      {!staleOnly && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
          <SearchInput value={q} onChange={setQ} placeholder="Search people, roles, brands\u2026" />
          <FilterChip label="Sector" value={sector} onChange={setSector} options={sectors} allLabel="All sectors" />
          <FilterChip label="Status" value={verif} onChange={setVerif}
            options={[
              { value: 'verified', label: 'Verified' },
              { value: 'unverified', label: 'Unverified' },
              { value: 'stale', label: 'Stale' },
              { value: 'bounced', label: 'Bounced' },
            ]} allLabel="Any status" />
          <FilterChip label="Has email" value={hasEmail} onChange={setHasEmail}
            options={[{ value: true, label: 'Yes' }, { value: false, label: 'No' }]} allLabel="Any" />
          <FilterChip label="Last contacted" value={recency} onChange={setRecency}
            options={[
              { value: 'week', label: 'Past 7 days' },
              { value: 'month', label: 'Past 30 days' },
              { value: 'never', label: 'Never' },
            ]} allLabel="Any time" />
          <div style={{ marginLeft: 'auto', fontSize: 12.5, color: 'var(--text-secondary)' }}>
            {filtered.length} of {contacts.length}
          </div>
        </div>
      )}

      {staleOnly && (
        <div style={{
          padding: '14px 16px', borderRadius: 12,
          background: '#FDF5E7', border: '1px solid #F3DFA6',
          display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16,
        }}>
          <Sparkles size={18} color="#8A6417" />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: '#8A6417' }}>
              {filtered.length} contacts need attention
            </div>
            <div style={{ fontSize: 12.5, color: '#8A6417', marginTop: 2, opacity: 0.85 }}>
              Unverified for 90+ days, bounced on last send, or flagged via LinkedIn re-check. Re-enrich or archive.
            </div>
          </div>
          <button className="btn-industrial-secondary text-xs px-3 py-1.5 rounded-lg" onClick={() => onToast(`Re-enriching ${filtered.length} contacts\u2026`)}>
            Re-enrich all
          </button>
        </div>
      )}

      <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', borderRadius: 14, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: 'var(--bg-tertiary)', borderBottom: '1px solid var(--border-default)' }}>
              <th style={thStyle(48)}>
                <input type="checkbox" checked={allSelected} onChange={toggleAll} style={{ cursor: 'pointer' }} />
              </th>
              <th style={thStyle()}>Name</th>
              <th style={thStyle(220)}>Role</th>
              <th style={thStyle(200)}>Company</th>
              <th style={thStyle(230)}>Email</th>
              <th style={thStyle(140)}>Last contacted</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(ct => {
              const co = companiesById[ct.company_id];
              return (
                <tr key={ct.id} onClick={() => onOpenContact(ct.id)}
                  className="hover:bg-[var(--bg-tertiary)] transition-colors"
                  style={{ borderBottom: '1px solid var(--border-default)', cursor: 'pointer' }}>
                  <td style={tdStyle()} onClick={e => e.stopPropagation()}>
                    <input type="checkbox" checked={selected.has(ct.id)} onChange={() => toggleSel(ct.id)} style={{ cursor: 'pointer' }} />
                  </td>
                  <td style={tdStyle()}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <ContactAvatar contact={ct} size={32} />
                      <div style={{ minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{contactFullName(ct)}</span>
                          {(ct.verif === 'stale' || ct.verif === 'bounced') && <VerifPill status={ct.verif} sm />}
                        </div>
                        {ct.linkedin && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>LinkedIn</div>}
                      </div>
                    </div>
                  </td>
                  <td style={tdStyle()}>
                    <span style={{ color: 'var(--text-secondary)' }}>{ct.role}</span>
                  </td>
                  <td style={tdStyle()} onClick={e => { e.stopPropagation(); onOpenCompany(co.id); }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <CompanyLogo company={co} size={24} radius={6} />
                      <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{co?.name}</span>
                    </div>
                  </td>
                  <td style={tdStyle()}>
                    {ct.email ? (
                      <span className="font-mono" style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{ct.email}</span>
                    ) : (
                      <span style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>No email</span>
                    )}
                  </td>
                  <td style={tdStyle()}>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ color: ct.last_contacted_days !== null && ct.last_contacted_days < 30 ? 'var(--text-primary)' : 'var(--text-muted)', fontSize: 12.5 }}>
                        {formatRelDays(ct.last_contacted_days)}
                      </span>
                      {ct.last_reply_days !== null && ct.last_reply_days !== undefined && (
                        <span style={{ fontSize: 11, color: '#2F7A3B', marginTop: 1 }}>&crarr; replied {formatRelDays(ct.last_reply_days)}</span>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <SelectionBar count={selected.size} kind="contact"
        onClear={() => setSelected(new Set())}
        onSend={() => { onToast(`${selected.size} contacts added to Outreach campaign draft`); setSelected(new Set()); }}
        onEnrich={() => { onToast(`Enrichment queued for ${selected.size} contacts`); setSelected(new Set()); }} />
    </div>
  );
}

// ---- Directory (main export) ----
export function Directory({ onOpenCompany, onOpenContact, onToast }: {
  onOpenCompany: (id: string) => void;
  onOpenContact: (id: string) => void;
  onToast: (msg: string) => void;
}) {
  const [tab, setTab] = useState('companies');

  const staleCount = contacts.filter(c => c.verif === 'stale' || c.verif === 'bounced').length;
  const counts = { companies: companies.length, contacts: contacts.length, stale: staleCount };

  return (
    <div>
      <Tabs tab={tab} setTab={setTab} counts={counts} />
      {tab === 'companies' && <CompaniesTable onOpenCompany={onOpenCompany} onToast={onToast} />}
      {tab === 'contacts' && <ContactsTable onOpenContact={onOpenContact} onOpenCompany={onOpenCompany} onToast={onToast} />}
      {tab === 'stale' && <ContactsTable onOpenContact={onOpenContact} onOpenCompany={onOpenCompany} onToast={onToast} staleOnly />}
    </div>
  );
}
