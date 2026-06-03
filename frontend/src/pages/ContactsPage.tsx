import { useState, useCallback, useRef } from 'react';
import { Plus, Upload, X } from 'lucide-react';
import { Directory } from './contacts/Directory';
import { CompanyDetailPage } from './contacts/CompanyDetail';
import { ContactDetailPage } from './contacts/ContactDetail';
import { Toast } from './contacts/ui';
import { AppLayout } from '../components/Layout/AppLayout';
import { useCreateContact, useImportContacts } from '../hooks/useContacts';

type View =
  | { kind: 'directory' }
  | { kind: 'company'; id: string }
  | { kind: 'contact'; id: string };

export function ContactsPage() {
  const [view, setView] = useState<View>({ kind: 'directory' });
  const [toast, setToast] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const onToast = useCallback((msg: string) => setToast(msg), []);
  const clearToast = useCallback(() => setToast(null), []);

  const openCompany = useCallback((id: string) => setView({ kind: 'company', id }), []);
  const openContact = useCallback((id: string) => setView({ kind: 'contact', id }), []);
  const backToDirectory = useCallback(() => setView({ kind: 'directory' }), []);

  const importContacts = useImportContacts();

  const onFilePicked = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    // Reset so picking the same file again re-triggers onChange.
    e.target.value = '';
    if (!file) return;
    importContacts.mutate(file, {
      onSuccess: (r) =>
        onToast(
          `Imported ${r.imported} contacts · ${r.companies_created} new companies${r.failed ? ` · ${r.failed} failed` : ''}`,
        ),
      onError: () => onToast('Import failed — check the file format'),
    });
  };

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
      {view.kind === 'directory' && (
        <>
          {/* Header */}
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="font-display text-2xl font-semibold text-[var(--text-primary)]">
                Contacts
              </h1>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                Companies and contacts in your CRE network
              </p>
            </div>
            <div className="flex items-center gap-3">
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.xlsx"
                className="hidden"
                onChange={onFilePicked}
              />
              <button
                className="btn-industrial-secondary text-sm px-4 py-2 rounded-lg flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={importContacts.isPending}
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="h-4 w-4" />
                {importContacts.isPending ? 'Importing…' : 'Import CSV'}
              </button>
              <button
                className="btn-industrial-primary text-sm px-4 py-2 rounded-lg flex items-center gap-1.5"
                onClick={() => setAddOpen(true)}
              >
                <Plus className="h-4 w-4" />
                Add contact
              </button>
            </div>
          </div>

          <Directory
            onOpenCompany={openCompany}
            onOpenContact={openContact}
            onToast={onToast}
          />
        </>
      )}

      {view.kind === 'company' && (
        <CompanyDetailPage
          companyId={view.id}
          onBack={backToDirectory}
          onOpenContact={openContact}
          onToast={onToast}
        />
      )}

      {view.kind === 'contact' && (
        <ContactDetailPage
          contactId={view.id}
          onBack={backToDirectory}
          onOpenCompany={openCompany}
          onToast={onToast}
        />
      )}

          <Toast msg={toast} onClose={clearToast} />
        </div>
      </div>
      {addOpen && (
        <AddContactModal
          onClose={() => setAddOpen(false)}
          onToast={onToast}
        />
      )}
    </AppLayout>
  );
}

// ---- Add contact modal ----
function AddContactModal({ onClose, onToast }: {
  onClose: () => void;
  onToast: (msg: string) => void;
}) {
  const [first, setFirst] = useState('');
  const [last, setLast] = useState('');
  const [role, setRole] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [company, setCompany] = useState('');
  const createContact = useCreateContact();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!first.trim()) return;
    createContact.mutate(
      {
        first: first.trim(),
        last: last.trim() || undefined,
        role: role.trim() || undefined,
        email: email.trim() || undefined,
        phone: phone.trim() || undefined,
        company_name: company.trim() || undefined,
      },
      {
        onSuccess: () => {
          onToast('Contact added');
          onClose();
        },
      },
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/30 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative w-full max-w-md mx-4 bg-[var(--bg-elevated)] rounded-2xl border border-[var(--border-default)] shadow-xl animate-scale-in">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-subtle)]">
          <h2 className="text-base font-semibold text-industrial">
            Add contact
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-industrial-muted hover:bg-[var(--bg-tertiary)] transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-industrial mb-1.5">
                First name
              </label>
              <input
                type="text"
                value={first}
                onChange={(e) => setFirst(e.target.value)}
                placeholder="Jane"
                className="w-full px-3 py-2.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)]/50 transition-colors"
                autoFocus
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-industrial mb-1.5">
                Last name
                <span className="text-industrial-muted font-normal ml-1">
                  (optional)
                </span>
              </label>
              <input
                type="text"
                value={last}
                onChange={(e) => setLast(e.target.value)}
                placeholder="Doe"
                className="w-full px-3 py-2.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)]/50 transition-colors"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-industrial mb-1.5">
              Role
              <span className="text-industrial-muted font-normal ml-1">
                (optional)
              </span>
            </label>
            <input
              type="text"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="e.g. Director of Real Estate"
              className="w-full px-3 py-2.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)]/50 transition-colors"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-industrial mb-1.5">
                Email
                <span className="text-industrial-muted font-normal ml-1">
                  (optional)
                </span>
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="jane@brand.com"
                className="w-full px-3 py-2.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)]/50 transition-colors"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-industrial mb-1.5">
                Phone
                <span className="text-industrial-muted font-normal ml-1">
                  (optional)
                </span>
              </label>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="(212) 555-0100"
                className="w-full px-3 py-2.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)]/50 transition-colors"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-industrial mb-1.5">
              Company
              <span className="text-industrial-muted font-normal ml-1">
                (optional)
              </span>
            </label>
            <input
              type="text"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="e.g. Sweetgreen"
              className="w-full px-3 py-2.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)]/50 transition-colors"
            />
            <p className="mt-2 text-xs text-industrial-muted">
              We&rsquo;ll attach this contact to the matching company, or create it if it&rsquo;s new.
            </p>
          </div>

          {createContact.isError && (
            <p className="text-xs text-[var(--color-error)]">
              Couldn&rsquo;t add the contact. Please try again.
            </p>
          )}

          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm font-medium text-industrial-secondary hover:bg-[var(--bg-tertiary)] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!first.trim() || createContact.isPending}
              className="px-4 py-2 rounded-lg text-sm font-semibold bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {createContact.isPending ? 'Adding…' : 'Add contact'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
