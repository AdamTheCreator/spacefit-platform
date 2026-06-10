import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles } from 'lucide-react';
import type { Company, Contact } from './data';
import type { CreateRecipientRequest } from '../../types/outreach';
import {
  contactFullName, formatRelDays, formatSF,
} from './data';
import {
  CompanyLogo, ContactAvatar, VerifPill, ExpansionBadge, FilterChip, SelectionBar,
} from './ui';
import { DataTable, type Column } from '../../components/ui/DataTable';
import { FilterBar } from '../../components/ui/FilterBar';
import { useCompanies, useContacts } from '../../hooks/useContacts';

type CompaniesById = Record<string, Company>;
type ContactsForCompany = (companyId: string) => Contact[];

// ---- Tabs ----
function Tabs({ tab, setTab, counts }: {
  tab: string; setTab: (t: string) => void;
  counts: { companies: number; contacts: number; stale: number };
}) {
  const items = [
    { id: 'companies', label: 'Companies', count: counts.companies, pill: false },
    { id: 'contacts', label: 'Contacts', count: counts.contacts, pill: false },
    { id: 'stale', label: 'Needs attention', count: counts.stale, pill: true },
  ];
  return (
    <div className="flex gap-0.5 border-b border-[var(--border-default)] mb-[18px]">
      {items.map(it => (
        <button
          key={it.id}
          onClick={() => setTab(it.id)}
          className={`flex items-center gap-2 px-3.5 py-2.5 text-[13.5px] -mb-px border-b-2 transition-colors ${
            tab === it.id
              ? 'font-semibold text-[var(--text-primary)] border-[var(--accent)]'
              : 'font-medium text-[var(--text-secondary)] border-transparent hover:text-[var(--text-primary)]'
          }`}
        >
          {it.label}
          <span className={`text-[11px] px-1.5 py-px rounded-full font-medium ${
            it.pill && it.count > 0
              ? 'bg-[var(--bg-error)] text-[var(--color-error)]'
              : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)]'
          }`}>{it.count}</span>
        </button>
      ))}
    </div>
  );
}

// ---- Companies table ----
function CompaniesTable({ companies, contactsForCompany, onOpenCompany, onToast }: {
  companies: Company[];
  contactsForCompany: ContactsForCompany;
  onOpenCompany: (id: string) => void; onToast: (msg: string) => void;
}) {
  const [q, setQ] = useState('');
  const [sector, setSector] = useState<string | null>(null);
  const [expanding, setExpanding] = useState<boolean | null>(null);
  const [market, setMarket] = useState<string | null>(null);
  const [sfBucket, setSfBucket] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const navigate = useNavigate();

  const sectors = useMemo(() => [...new Set(companies.map(c => c.sector))].map(s => ({ value: s, label: s })), [companies]);
  const markets = useMemo(() => {
    const all = new Set<string>();
    companies.forEach(c => (c.target_markets || []).forEach(m => all.add(m)));
    return [...all].sort().map(m => ({ value: m, label: m }));
  }, [companies]);

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
  }, [companies, q, sector, expanding, market, sfBucket]);

  const toggleSel = (id: string) => setSelected(s => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const allSelected = filtered.length > 0 && filtered.every(c => selected.has(c.id));
  const toggleAll = () => {
    if (allSelected) setSelected(new Set());
    else setSelected(new Set(filtered.map(c => c.id)));
  };

  const columns: Column<Company>[] = [
    {
      key: 'name', header: 'Brand',
      sortValue: (c) => c.name.toLowerCase(),
      render: (c) => (
        <div className="flex items-center gap-3">
          <CompanyLogo company={c} size={36} />
          <div className="min-w-0">
            <div className="font-semibold text-[var(--text-primary)] text-[13.5px]">{c.name}</div>
            <div className="text-[11.5px] text-[var(--text-muted)] mt-px">{c.website}</div>
          </div>
        </div>
      ),
    },
    {
      key: 'sector', header: 'Sector', width: 160,
      sortValue: (c) => c.sector,
      render: (c) => (
        <>
          <div className="text-[var(--text-secondary)]">{c.sector}</div>
          {c.subsector && <div className="text-[11.5px] text-[var(--text-muted)]">{c.subsector}</div>}
        </>
      ),
    },
    {
      key: 'locations', header: 'Locations', width: 120, align: 'right',
      sortValue: (c) => c.us_locations ?? -1,
      render: (c) => (
        <span>
          <span className="text-[var(--text-primary)] font-medium">{c.us_locations?.toLocaleString() || '—'}</span>
          <span className="text-[var(--text-muted)] text-[11.5px] ml-1">US</span>
        </span>
      ),
    },
    {
      key: 'sf', header: 'Typical SF', width: 130,
      sortValue: (c) => (((c.sf_min || 0) + (c.sf_max || 0)) / 2) || null,
      render: (c) => <span className="text-[var(--text-secondary)]">{formatSF(c.sf_min, c.sf_max)}</span>,
    },
    {
      key: 'expanding', header: 'Expanding', width: 140,
      sortValue: (c) => (c.is_expanding === true ? 2 : c.is_expanding === false ? 1 : 0),
      render: (c) => <ExpansionBadge value={c.is_expanding} />,
    },
    {
      key: 'contacts', header: 'Contacts', width: 150,
      sortValue: (c) => contactsForCompany(c.id).length,
      render: (c) => {
        const cts = contactsForCompany(c.id);
        const verifCount = cts.filter(x => x.verif === 'verified').length;
        const staleCount = cts.filter(x => x.verif === 'stale' || x.verif === 'bounced').length;
        return (
          <div className="flex items-center gap-1.5">
            <span className="text-[var(--text-primary)] font-medium">{cts.length}</span>
            <span className="text-[var(--text-muted)] text-[11.5px]">· {verifCount} verified</span>
            {staleCount > 0 && (
              <span className="text-[var(--color-warning)] text-[11px] font-medium">· {staleCount} stale</span>
            )}
          </div>
        );
      },
    },
    {
      key: 'last', header: 'Last activity', width: 120,
      sortValue: (c) => {
        const m = Math.min(...contactsForCompany(c.id).map(x => x.last_contacted_days ?? 9999));
        return m === 9999 ? null : m;
      },
      render: (c) => {
        const lastContacted = Math.min(...contactsForCompany(c.id).map(x => x.last_contacted_days ?? 9999));
        return (
          <span className={`text-[12.5px] ${lastContacted < 30 ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'}`}>
            {formatRelDays(lastContacted === 9999 ? null : lastContacted)}
          </span>
        );
      },
    },
  ];

  return (
    <div>
      <FilterBar
        search={{ value: q, onChange: setQ, placeholder: 'Search companies…' }}
        trailing={`${filtered.length} of ${companies.length}`}
      >
        <FilterChip label="Sector" value={sector} onChange={setSector} options={sectors} allLabel="All sectors" />
        <FilterChip label="Expanding" value={expanding} onChange={setExpanding}
          options={[{ value: true, label: 'Yes' }, { value: false, label: 'No' }]} allLabel="Any" />
        <FilterChip label="Market" value={market} onChange={setMarket} options={markets} allLabel="All markets" />
        <FilterChip label="Size" value={sfBucket} onChange={setSfBucket}
          options={[{ value: 'sm', label: '< 2K sf' }, { value: 'md', label: '2–3.5K sf' }, { value: 'lg', label: '3.5K+ sf' }]}
          allLabel="Any size" />
      </FilterBar>

      <DataTable
        columns={columns}
        rows={filtered}
        rowKey={(c) => c.id}
        onRowClick={(c) => onOpenCompany(c.id)}
        initialSort={{ key: 'name', dir: 'asc' }}
        selectable
        isSelected={(c) => selected.has(c.id)}
        onToggleRow={(c) => toggleSel(c.id)}
        allSelected={allSelected}
        onToggleAll={toggleAll}
        empty="No companies match your filters."
      />

      <SelectionBar count={selected.size} kind="company"
        onClear={() => setSelected(new Set())}
        onSend={() => {
          const recips: CreateRecipientRequest[] = [];
          for (const id of selected) {
            const co = companies.find(c => c.id === id);
            if (!co) continue;
            for (const ct of contactsForCompany(id)) {
              if (!ct.email) continue;
              recips.push({
                tenant_name: co.name,
                contact_email: ct.email,
                contact_name: contactFullName(ct),
                contact_title: ct.role || undefined,
              });
            }
          }
          if (recips.length === 0) {
            onToast('No contacts with an email at the selected companies');
            return;
          }
          navigate('/outreach', { state: { composeRecipients: recips } });
        }}
        onEnrich={() => { onToast(`Enrichment queued for ${selected.size} companies`); setSelected(new Set()); }} />
    </div>
  );
}

// ---- Contacts table ----
function ContactsTable({ contacts, companies, companiesById, onOpenContact, onOpenCompany, onToast, staleOnly = false }: {
  contacts: Contact[];
  companies: Company[];
  companiesById: CompaniesById;
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
  const navigate = useNavigate();

  const sectors = useMemo(() => [...new Set(companies.map(c => c.sector))].map(s => ({ value: s, label: s })), [companies]);

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
  }, [contacts, companiesById, q, sector, verif, hasEmail, recency]);

  const toggleSel = (id: string) => setSelected(s => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const allSelected = filtered.length > 0 && filtered.every(c => selected.has(c.id));
  const toggleAll = () => {
    if (allSelected) setSelected(new Set());
    else setSelected(new Set(filtered.map(c => c.id)));
  };

  const columns: Column<Contact>[] = [
    {
      key: 'name', header: 'Name',
      sortValue: (ct) => contactFullName(ct).toLowerCase(),
      render: (ct) => (
        <div className="flex items-center gap-2.5">
          <ContactAvatar contact={ct} size={32} />
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="font-semibold text-[var(--text-primary)]">{contactFullName(ct)}</span>
              {(ct.verif === 'stale' || ct.verif === 'bounced') && <VerifPill status={ct.verif} sm />}
            </div>
            {ct.linkedin && <div className="text-[11px] text-[var(--text-muted)] mt-px">LinkedIn</div>}
          </div>
        </div>
      ),
    },
    {
      key: 'role', header: 'Role', width: 220,
      sortValue: (ct) => ct.role,
      render: (ct) => <span className="text-[var(--text-secondary)]">{ct.role}</span>,
    },
    {
      key: 'company', header: 'Company', width: 200,
      sortValue: (ct) => companiesById[ct.company_id]?.name ?? '',
      render: (ct) => {
        const co = companiesById[ct.company_id];
        return co ? (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onOpenCompany(co.id); }}
            className="flex items-center gap-2 hover:underline"
          >
            <CompanyLogo company={co} size={24} radius={6} />
            <span className="text-[var(--text-primary)] font-medium">{co.name}</span>
          </button>
        ) : (
          <span className="text-[var(--text-muted)] text-[12.5px]">—</span>
        );
      },
    },
    {
      key: 'email', header: 'Email', width: 230,
      sortValue: (ct) => ct.email ?? null,
      render: (ct) => ct.email ? (
        <span className="font-mono text-[12px] text-[var(--text-secondary)]">{ct.email}</span>
      ) : (
        <span className="text-[12px] text-[var(--text-muted)] italic">No email</span>
      ),
    },
    {
      key: 'last', header: 'Last contacted', width: 140,
      sortValue: (ct) => ct.last_contacted_days,
      render: (ct) => (
        <div className="flex flex-col">
          <span className={`text-[12.5px] ${ct.last_contacted_days !== null && ct.last_contacted_days < 30 ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'}`}>
            {formatRelDays(ct.last_contacted_days)}
          </span>
          {ct.last_reply_days !== null && ct.last_reply_days !== undefined && (
            <span className="text-[11px] text-[var(--color-success)] mt-px">↵ replied {formatRelDays(ct.last_reply_days)}</span>
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      {!staleOnly && (
        <FilterBar
          search={{ value: q, onChange: setQ, placeholder: 'Search people, roles, brands…' }}
          trailing={`${filtered.length} of ${contacts.length}`}
        >
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
        </FilterBar>
      )}

      {staleOnly && (
        <div className="flex items-center gap-3 mb-4 px-4 py-3.5 rounded-xl bg-[var(--bg-warning)] border border-[var(--color-warning)]/30">
          <Sparkles size={18} className="text-[var(--color-warning)] flex-shrink-0" />
          <div className="flex-1">
            <div className="text-[13.5px] font-semibold text-[var(--color-warning)]">
              {filtered.length} contacts need attention
            </div>
            <div className="text-[12.5px] text-[var(--color-warning)] mt-0.5 opacity-85">
              Unverified for 90+ days, bounced on last send, or flagged via LinkedIn re-check. Re-enrich or archive.
            </div>
          </div>
          <button className="btn-industrial-secondary text-xs px-3 py-1.5 rounded-lg" onClick={() => onToast(`Re-enriching ${filtered.length} contacts…`)}>
            Re-enrich all
          </button>
        </div>
      )}

      <DataTable
        columns={columns}
        rows={filtered}
        rowKey={(ct) => ct.id}
        onRowClick={(ct) => onOpenContact(ct.id)}
        initialSort={{ key: 'name', dir: 'asc' }}
        selectable
        isSelected={(ct) => selected.has(ct.id)}
        onToggleRow={(ct) => toggleSel(ct.id)}
        allSelected={allSelected}
        onToggleAll={toggleAll}
        empty={staleOnly ? 'No contacts need attention right now.' : 'No contacts match your filters.'}
      />

      <SelectionBar count={selected.size} kind="contact"
        onClear={() => setSelected(new Set())}
        onSend={() => {
          const recips: CreateRecipientRequest[] = [];
          for (const id of selected) {
            const ct = contacts.find(c => c.id === id);
            if (!ct || !ct.email) continue;
            const co = companiesById[ct.company_id];
            recips.push({
              tenant_name: co?.name || contactFullName(ct),
              contact_email: ct.email,
              contact_name: contactFullName(ct),
              contact_title: ct.role || undefined,
            });
          }
          if (recips.length === 0) {
            onToast('Selected contacts have no email address');
            return;
          }
          navigate('/outreach', { state: { composeRecipients: recips } });
        }}
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

  const companiesQuery = useCompanies();
  const contactsQuery = useContacts();
  const companies = useMemo(() => companiesQuery.data ?? [], [companiesQuery.data]);
  const contacts = useMemo(() => contactsQuery.data ?? [], [contactsQuery.data]);

  const companiesById = useMemo<CompaniesById>(
    () => Object.fromEntries(companies.map(c => [c.id, c])),
    [companies],
  );
  const contactsForCompany = useMemo<ContactsForCompany>(
    () => (companyId: string) => contacts.filter(c => c.company_id === companyId),
    [contacts],
  );

  const isLoading = companiesQuery.isLoading || contactsQuery.isLoading;

  if (isLoading) {
    return (
      <div style={{ padding: '64px 20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13.5 }}>
        Loading contacts…
      </div>
    );
  }

  if (companies.length === 0 && contacts.length === 0) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center',
        gap: 14, padding: '56px 24px', maxWidth: 440, margin: '24px auto',
        background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', borderRadius: 16,
      }}>
        <img src="/mascots/goose-planner.webp" alt="" width={96} height={96} style={{ opacity: 0.95 }} />
        <h3 className="font-display" style={{ fontSize: 18, color: 'var(--text-primary)' }}>No contacts yet</h3>
        <p style={{ fontSize: 13.5, color: 'var(--text-secondary)', lineHeight: 1.55, margin: 0 }}>
          Build your CRE network here. Use <strong>Add contact</strong> or <strong>Import CSV</strong> in the
          page header to get started.
        </p>
      </div>
    );
  }

  const staleCount = contacts.filter(c => c.verif === 'stale' || c.verif === 'bounced').length;
  const counts = { companies: companies.length, contacts: contacts.length, stale: staleCount };

  return (
    <div>
      <Tabs tab={tab} setTab={setTab} counts={counts} />
      {tab === 'companies' && (
        <CompaniesTable
          companies={companies}
          contactsForCompany={contactsForCompany}
          onOpenCompany={onOpenCompany}
          onToast={onToast}
        />
      )}
      {tab === 'contacts' && (
        <ContactsTable
          contacts={contacts}
          companies={companies}
          companiesById={companiesById}
          onOpenContact={onOpenContact}
          onOpenCompany={onOpenCompany}
          onToast={onToast}
        />
      )}
      {tab === 'stale' && (
        <ContactsTable
          contacts={contacts}
          companies={companies}
          companiesById={companiesById}
          onOpenContact={onOpenContact}
          onOpenCompany={onOpenCompany}
          onToast={onToast}
          staleOnly
        />
      )}
    </div>
  );
}
