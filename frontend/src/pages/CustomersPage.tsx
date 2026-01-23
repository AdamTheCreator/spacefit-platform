import { AppLayout } from '../components/Layout';
import { Users, Plus, Upload } from 'lucide-react';

export function CustomersPage() {
  return (
    <AppLayout>
      <div className="p-6 bg-industrial min-h-full">
        <div className="flex items-center justify-between mb-6">
          <h1 className="font-mono text-lg font-bold tracking-tight text-industrial">Customers</h1>
          <div className="flex gap-3">
            <button className="btn-industrial">
              <Upload size={16} />
              Import
            </button>
            <button className="btn-industrial-primary">
              <Plus size={16} />
              Add Customer
            </button>
          </div>
        </div>

        <div className="card-industrial">
          <div className="p-8 text-center">
            <div className="w-16 h-16 bg-[var(--bg-tertiary)] border border-industrial flex items-center justify-center mx-auto mb-4">
              <Users size={32} className="text-industrial-muted" />
            </div>
            <h2 className="font-mono text-sm font-semibold uppercase tracking-wide text-industrial mb-2">
              No customers yet
            </h2>
            <p className="font-mono text-xs text-industrial-muted mb-6 max-w-md mx-auto">
              Add your clients and prospects to send them targeted notifications
              about property opportunities.
            </p>
            <div className="flex gap-3 justify-center">
              <button className="btn-industrial">
                <Upload size={16} />
                Import from CSV
              </button>
              <button className="btn-industrial-primary">
                <Plus size={16} />
                Add Manually
              </button>
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
