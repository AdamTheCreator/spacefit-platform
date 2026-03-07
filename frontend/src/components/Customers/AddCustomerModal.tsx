import { useState, useEffect, useCallback } from 'react';
import { X, UserPlus } from 'lucide-react';
import { Button } from '../ui/Button';
import { useCreateCustomer, type CreateCustomerData } from '../../hooks/useCustomers';

interface AddCustomerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const INITIAL_FORM: CreateCustomerData = {
  name: '',
  company_name: '',
  email: '',
  phone: '',
  address: '',
  city: '',
  state: '',
  zip_code: '',
};

export function AddCustomerModal({ isOpen, onClose, onSuccess }: AddCustomerModalProps) {
  const [form, setForm] = useState<CreateCustomerData>(INITIAL_FORM);
  const [error, setError] = useState<string | null>(null);

  const createMutation = useCreateCustomer();

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setForm(INITIAL_FORM);
      setError(null);
      createMutation.reset();
    }
  }, [isOpen]);

  // Handle Escape key
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !createMutation.isPending) {
        onClose();
      }
    },
    [isOpen, createMutation.isPending, onClose],
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!form.name.trim()) {
      setError('Name is required');
      return;
    }

    // Clean up empty strings to undefined
    const data: CreateCustomerData = {
      name: form.name.trim(),
      company_name: form.company_name?.trim() || undefined,
      email: form.email?.trim() || undefined,
      phone: form.phone?.trim() || undefined,
      address: form.address?.trim() || undefined,
      city: form.city?.trim() || undefined,
      state: form.state?.trim() || undefined,
      zip_code: form.zip_code?.trim() || undefined,
    };

    try {
      await createMutation.mutateAsync(data);
      onSuccess();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create customer');
    }
  };

  const handleClose = () => {
    if (!createMutation.isPending) {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className="relative bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-subtle)]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-[var(--accent)]/10 rounded-lg flex items-center justify-center">
              <UserPlus size={16} className="text-[var(--accent)]" />
            </div>
            <h2 className="font-mono text-sm font-semibold uppercase tracking-wide text-industrial">
              Add Customer
            </h2>
          </div>
          <button
            onClick={handleClose}
            disabled={createMutation.isPending}
            className="p-1.5 rounded-lg hover:bg-[var(--bg-tertiary)] text-industrial-muted hover:text-industrial transition-colors disabled:opacity-50"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          {/* Name (required) */}
          <div>
            <label className="block text-xs font-medium text-industrial-muted mb-1.5">
              Name <span className="text-[var(--color-error)]">*</span>
            </label>
            <input
              type="text"
              name="name"
              value={form.name}
              onChange={handleChange}
              placeholder="John Smith"
              className="input-industrial w-full"
              autoFocus
            />
          </div>

          {/* Company */}
          <div>
            <label className="block text-xs font-medium text-industrial-muted mb-1.5">
              Company
            </label>
            <input
              type="text"
              name="company_name"
              value={form.company_name}
              onChange={handleChange}
              placeholder="Acme Corporation"
              className="input-industrial w-full"
            />
          </div>

          {/* Email & Phone - 2 columns */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-industrial-muted mb-1.5">
                Email
              </label>
              <input
                type="email"
                name="email"
                value={form.email}
                onChange={handleChange}
                placeholder="john@example.com"
                className="input-industrial w-full"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-industrial-muted mb-1.5">
                Phone
              </label>
              <input
                type="tel"
                name="phone"
                value={form.phone}
                onChange={handleChange}
                placeholder="(555) 123-4567"
                className="input-industrial w-full"
              />
            </div>
          </div>

          {/* Address */}
          <div>
            <label className="block text-xs font-medium text-industrial-muted mb-1.5">
              Address
            </label>
            <input
              type="text"
              name="address"
              value={form.address}
              onChange={handleChange}
              placeholder="123 Main Street"
              className="input-industrial w-full"
            />
          </div>

          {/* City, State, Zip - 3 columns */}
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-industrial-muted mb-1.5">
                City
              </label>
              <input
                type="text"
                name="city"
                value={form.city}
                onChange={handleChange}
                placeholder="Austin"
                className="input-industrial w-full"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-industrial-muted mb-1.5">
                State
              </label>
              <input
                type="text"
                name="state"
                value={form.state}
                onChange={handleChange}
                placeholder="TX"
                className="input-industrial w-full"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-industrial-muted mb-1.5">
                Zip Code
              </label>
              <input
                type="text"
                name="zip_code"
                value={form.zip_code}
                onChange={handleChange}
                placeholder="78701"
                className="input-industrial w-full"
              />
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="p-3 bg-[var(--color-error)]/10 rounded-lg border border-[var(--color-error)]/30">
              <p className="text-sm text-[var(--color-error)]">{error}</p>
            </div>
          )}
        </form>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-[var(--border-subtle)] flex items-center justify-end gap-3">
          <Button
            variant="ghost"
            onClick={handleClose}
            disabled={createMutation.isPending}
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            disabled={createMutation.isPending}
            loading={createMutation.isPending}
            iconLeft={<UserPlus size={16} />}
          >
            Add Customer
          </Button>
        </div>
      </div>
    </div>
  );
}
