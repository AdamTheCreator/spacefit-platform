import { useState } from 'react';
import { AppLayout } from '../components/Layout';
import { Button } from '../components/ui/Button';
import { ImportModal } from '../components/Customers/ImportModal';
import { AddCustomerModal } from '../components/Customers/AddCustomerModal';
import {
  useCustomers,
  useDeleteCustomer,
  type Customer,
} from '../hooks/useCustomers';
import {
  Users,
  Plus,
  Upload,
  Trash2,
  Building2,
  Mail,
  Phone,
  MapPin,
  AlertCircle,
  Loader2,
} from 'lucide-react';

function CustomerRow({
  customer,
  onDelete,
  isDeleting,
}: {
  customer: Customer;
  onDelete: (id: string) => void;
  isDeleting: boolean;
}) {
  const cityState = [customer.city, customer.state].filter(Boolean).join(', ');

  return (
    <tr className="border-b border-[var(--border-subtle)] hover:bg-[var(--bg-tertiary)] transition-colors">
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-[var(--accent)]/10 rounded-lg flex items-center justify-center flex-shrink-0">
            <Users size={14} className="text-[var(--accent)]" />
          </div>
          <span className="text-sm font-medium text-industrial">{customer.name}</span>
        </div>
      </td>
      <td className="px-4 py-3">
        {customer.company_name ? (
          <div className="flex items-center gap-2 text-sm text-industrial-secondary">
            <Building2 size={14} className="text-industrial-muted flex-shrink-0" />
            {customer.company_name}
          </div>
        ) : (
          <span className="text-xs text-industrial-muted">—</span>
        )}
      </td>
      <td className="px-4 py-3">
        {customer.email ? (
          <div className="flex items-center gap-2 text-sm text-industrial-secondary">
            <Mail size={14} className="text-industrial-muted flex-shrink-0" />
            <a
              href={`mailto:${customer.email}`}
              className="hover:text-[var(--accent)] transition-colors"
            >
              {customer.email}
            </a>
          </div>
        ) : (
          <span className="text-xs text-industrial-muted">—</span>
        )}
      </td>
      <td className="px-4 py-3">
        {customer.phone ? (
          <div className="flex items-center gap-2 text-sm text-industrial-secondary font-mono">
            <Phone size={14} className="text-industrial-muted flex-shrink-0" />
            {customer.phone}
          </div>
        ) : (
          <span className="text-xs text-industrial-muted">—</span>
        )}
      </td>
      <td className="px-4 py-3">
        {cityState ? (
          <div className="flex items-center gap-2 text-sm text-industrial-secondary">
            <MapPin size={14} className="text-industrial-muted flex-shrink-0" />
            {cityState}
          </div>
        ) : (
          <span className="text-xs text-industrial-muted">—</span>
        )}
      </td>
      <td className="px-4 py-3 text-right">
        <button
          onClick={() => onDelete(customer.id)}
          disabled={isDeleting}
          className="p-1.5 rounded-lg text-industrial-muted hover:text-[var(--color-error)] hover:bg-[var(--color-error)]/10 transition-colors disabled:opacity-50"
        >
          {isDeleting ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <Trash2 size={16} />
          )}
        </button>
      </td>
    </tr>
  );
}

function EmptyState({
  onImport,
  onAdd,
}: {
  onImport: () => void;
  onAdd: () => void;
}) {
  return (
    <div className="card-industrial">
      <div className="p-8 text-center">
        <img
          src="/mascots/goose-carriers.webp"
          alt=""
          aria-hidden="true"
          className="w-28 h-28 mx-auto mb-3 object-contain select-none"
          draggable={false}
        />
        <h2 className="font-mono text-sm font-semibold uppercase tracking-wide text-industrial mb-2">
          No customers yet
        </h2>
        <p className="font-mono text-xs text-industrial-muted mb-6 max-w-md mx-auto">
          Bring your clients and prospects aboard — the crew will match them to property opportunities.
        </p>
        <div className="flex gap-3 justify-center">
          <Button variant="secondary" iconLeft={<Upload size={16} />} onClick={onImport}>
            Import from CSV
          </Button>
          <Button variant="primary" iconLeft={<Plus size={16} />} onClick={onAdd}>
            Add Manually
          </Button>
        </div>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="card-industrial">
      <div className="p-8 text-center">
        <Loader2 size={32} className="text-[var(--accent)] animate-spin mx-auto mb-4" />
        <p className="font-mono text-sm text-industrial-muted">Loading customers...</p>
      </div>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="card-industrial">
      <div className="p-8 text-center">
        <div className="w-16 h-16 bg-[var(--color-error)]/10 border border-[var(--color-error)]/30 rounded-xl flex items-center justify-center mx-auto mb-4">
          <AlertCircle size={32} className="text-[var(--color-error)]" />
        </div>
        <h2 className="font-mono text-sm font-semibold uppercase tracking-wide text-industrial mb-2">
          Failed to load customers
        </h2>
        <p className="font-mono text-xs text-industrial-muted mb-6 max-w-md mx-auto">
          {message}
        </p>
        <Button variant="secondary" onClick={onRetry}>
          Try Again
        </Button>
      </div>
    </div>
  );
}

export function CustomersPage() {
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const { data, isLoading, isError, error, refetch } = useCustomers();
  const deleteMutation = useDeleteCustomer();

  const customers = data?.items ?? [];
  const isEmpty = !isLoading && !isError && customers.length === 0;

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try {
      await deleteMutation.mutateAsync(id);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <AppLayout>
      <div className="p-6 bg-industrial min-h-full">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <h1 className="font-mono text-lg font-bold tracking-tight text-industrial">
              Customers
            </h1>
            {!isLoading && !isError && customers.length > 0 && (
              <span className="px-2 py-0.5 bg-[var(--bg-tertiary)] border border-[var(--border-subtle)] rounded-md text-xs font-mono text-industrial-muted">
                {data?.total ?? customers.length}
              </span>
            )}
          </div>
          <div className="flex gap-3">
            <Button
              variant="secondary"
              iconLeft={<Upload size={16} />}
              onClick={() => setImportModalOpen(true)}
            >
              Import
            </Button>
            <Button
              variant="primary"
              iconLeft={<Plus size={16} />}
              onClick={() => setAddModalOpen(true)}
            >
              Add Customer
            </Button>
          </div>
        </div>

        {/* Content */}
        {isLoading && <LoadingState />}

        {isError && (
          <ErrorState
            message={error instanceof Error ? error.message : 'Unknown error'}
            onRetry={() => refetch()}
          />
        )}

        {isEmpty && (
          <EmptyState
            onImport={() => setImportModalOpen(true)}
            onAdd={() => setAddModalOpen(true)}
          />
        )}

        {!isLoading && !isError && customers.length > 0 && (
          <div className="card-industrial overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[var(--border-default)] bg-[var(--bg-tertiary)]">
                    <th className="px-4 py-3 text-left text-xs font-mono font-semibold uppercase tracking-wide text-industrial-muted">
                      Name
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-mono font-semibold uppercase tracking-wide text-industrial-muted">
                      Company
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-mono font-semibold uppercase tracking-wide text-industrial-muted">
                      Email
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-mono font-semibold uppercase tracking-wide text-industrial-muted">
                      Phone
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-mono font-semibold uppercase tracking-wide text-industrial-muted">
                      City/State
                    </th>
                    <th className="px-4 py-3 w-12"></th>
                  </tr>
                </thead>
                <tbody>
                  {customers.map((customer) => (
                    <CustomerRow
                      key={customer.id}
                      customer={customer}
                      onDelete={handleDelete}
                      isDeleting={deletingId === customer.id}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Modals */}
      <ImportModal
        isOpen={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        onSuccess={() => refetch()}
      />

      <AddCustomerModal
        isOpen={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        onSuccess={() => refetch()}
      />
    </AppLayout>
  );
}
