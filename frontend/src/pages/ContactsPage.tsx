import { useState, useCallback } from 'react';
import { Building2, Users, Plus } from 'lucide-react';
import { Directory } from './contacts/Directory';
import { CompanyDetailPage } from './contacts/CompanyDetail';
import { ContactDetailPage } from './contacts/ContactDetail';
import { Toast } from './contacts/ui';

type View =
  | { kind: 'directory' }
  | { kind: 'company'; id: string }
  | { kind: 'contact'; id: string };

export function ContactsPage() {
  const [view, setView] = useState<View>({ kind: 'directory' });
  const [toast, setToast] = useState<string | null>(null);

  const onToast = useCallback((msg: string) => setToast(msg), []);
  const clearToast = useCallback(() => setToast(null), []);

  const openCompany = useCallback((id: string) => setView({ kind: 'company', id }), []);
  const openContact = useCallback((id: string) => setView({ kind: 'contact', id }), []);
  const backToDirectory = useCallback(() => setView({ kind: 'directory' }), []);

  return (
    <div className="space-y-6">
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
              <button className="btn-industrial-primary text-sm px-4 py-2 rounded-lg flex items-center gap-1.5">
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
  );
}
