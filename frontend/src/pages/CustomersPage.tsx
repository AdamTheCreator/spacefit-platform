import { AppLayout } from '../components/Layout';
import { Users, Plus, Upload } from 'lucide-react';

export function CustomersPage() {
  return (
    <AppLayout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-white">Customers</h1>
          <div className="flex gap-3">
            <button className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors">
              <Upload size={18} />
              Import
            </button>
            <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
              <Plus size={18} />
              Add Customer
            </button>
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg border border-gray-700">
          <div className="p-8 text-center">
            <div className="w-16 h-16 bg-gray-700 rounded-full flex items-center justify-center mx-auto mb-4">
              <Users size={32} className="text-gray-500" />
            </div>
            <h2 className="text-lg font-medium text-gray-300 mb-2">
              No customers yet
            </h2>
            <p className="text-gray-500 mb-4 max-w-md mx-auto">
              Add your clients and prospects to send them targeted notifications
              about property opportunities.
            </p>
            <div className="flex gap-3 justify-center">
              <button className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors">
                <Upload size={18} />
                Import from CSV
              </button>
              <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
                <Plus size={18} />
                Add Manually
              </button>
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
