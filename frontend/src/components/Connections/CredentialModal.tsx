import { useState, useEffect, useCallback } from 'react';
import { X, Eye, EyeOff, Shield, Monitor, Trash2, BarChart3, Building2 } from 'lucide-react';
import type { SiteConfig, Credential } from '../../types/credentials';

// Map site IDs to Lucide icons
const SITE_ICONS: Record<string, React.ReactNode> = {
  siteusa: <BarChart3 size={20} className="text-[var(--accent)]" />,
  costar: <Building2 size={20} className="text-[var(--accent)]" />,
};

interface CredentialModalProps {
  isOpen: boolean;
  onClose: () => void;
  site: SiteConfig | null;
  existingCredential: Credential | null;
  onSave: (username: string, password: string) => Promise<void>;
  onDelete?: () => Promise<void>;
  isLoading: boolean;
  error: string | null;
}

export function CredentialModal({
  isOpen,
  onClose,
  site,
  existingCredential,
  onSave,
  onDelete,
  isLoading,
  error,
}: CredentialModalProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Reset form when modal opens/closes or site changes
  useEffect(() => {
    if (isOpen && existingCredential) {
      setUsername(existingCredential.username);
      setPassword('');
    } else if (isOpen) {
      setUsername('');
      setPassword('');
    }
    setLocalError(null);
    setShowPassword(false);
    setShowDeleteConfirm(false);
  }, [isOpen, existingCredential]);

  // Handle Escape key to close modal
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape' && isOpen) {
      onClose();
    }
  }, [isOpen, onClose]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  if (!isOpen || !site) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);

    if (!username.trim()) {
      setLocalError('Username/email is required');
      return;
    }

    if (!password.trim() && !existingCredential) {
      setLocalError('Password is required');
      return;
    }

    try {
      await onSave(username, password);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Failed to save credentials');
    }
  };

  const displayError = error || localError;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-[var(--bg-elevated)] border border-[var(--border-subtle)] rounded-2xl shadow-xl w-full max-w-md animate-scale-in">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-[var(--border-subtle)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[var(--bg-tertiary)] border border-[var(--border-subtle)] flex items-center justify-center">
              {SITE_ICONS[site.id] || <BarChart3 size={20} className="text-industrial-muted" />}
            </div>
            <div>
              <h2 id="modal-title" className="text-base font-semibold text-industrial">
                {existingCredential ? 'Update' : 'Connect to'} {site.name}
              </h2>
              {site.is_browser_based && (
                <p className="text-xs text-[var(--accent)] flex items-center gap-1 mt-0.5">
                  <Monitor size={12} aria-hidden="true" />
                  Browser-based connection
                </p>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close modal"
            className="p-2 rounded-lg text-industrial-muted hover:text-industrial hover:bg-[var(--hover-overlay)] transition-colors"
          >
            <X size={20} aria-hidden="true" />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {displayError && (
            <div className="p-3 rounded-lg bg-[var(--bg-error)] border border-[var(--color-error)]/20 text-sm text-[var(--color-error)]">
              {displayError}
            </div>
          )}

          <div>
            <label htmlFor="credential-username" className="text-sm font-medium text-industrial mb-2 block">
              Email / Username
            </label>
            <input
              id="credential-username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={`Enter your ${site.name} email`}
              className="input-industrial w-full"
              autoComplete="username"
              disabled={isLoading}
            />
          </div>

          <div>
            <label htmlFor="credential-password" className="text-sm font-medium text-industrial mb-2 block">
              Password
              {existingCredential && (
                <span className="text-industrial-muted font-normal ml-2">
                  (leave blank to keep current)
                </span>
              )}
            </label>
            <div className="relative">
              <input
                id="credential-password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={existingCredential ? '••••••••' : 'Enter password'}
                className="input-industrial w-full pr-12"
                autoComplete="current-password"
                disabled={isLoading}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded text-industrial-muted hover:text-industrial focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:ring-offset-2"
              >
                {showPassword ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
              </button>
            </div>
          </div>

          {/* Security info */}
          <div className="flex items-start gap-3 p-3 rounded-lg bg-[var(--bg-success)] border border-[var(--color-success)]/20">
            <Shield size={16} className="text-[var(--color-success)] mt-0.5 flex-shrink-0" aria-hidden="true" />
            <p className="text-xs text-industrial-secondary leading-relaxed">
              Your credentials are encrypted using AES-256 and stored securely.
              They are only used to access your {site.name} account on your behalf.
            </p>
          </div>

          {/* Browser automation info */}
          {site.is_browser_based && (
            <div className="flex items-start gap-3 p-3 rounded-lg bg-[var(--accent-subtle)] border border-[var(--accent)]/20">
              <Monitor size={16} className="text-[var(--accent)] mt-0.5 flex-shrink-0" aria-hidden="true" />
              <p className="text-xs text-industrial-secondary leading-relaxed">
                This connection uses browser automation. Queries will take
                approximately {site.typical_duration_seconds} seconds. You'll see
                progress updates during analysis.
              </p>
            </div>
          )}
        </form>

        {/* Footer */}
        <div className="flex gap-3 p-5 border-t border-[var(--border-subtle)]">
          {existingCredential && onDelete && (
            showDeleteConfirm ? (
              <div className="flex gap-2 flex-1">
                <button
                  type="button"
                  onClick={() => setShowDeleteConfirm(false)}
                  disabled={isLoading}
                  className="flex-1 px-4 py-2.5 rounded-lg border border-[var(--border-default)] text-sm font-medium text-industrial hover:bg-[var(--hover-overlay)] transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    await onDelete();
                    onClose();
                  }}
                  disabled={isLoading}
                  className="flex-1 px-4 py-2.5 rounded-lg bg-[var(--color-error)] hover:bg-[var(--color-error)]/90 text-white text-sm font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {isLoading ? (
                    <div className="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                  ) : (
                    <Trash2 size={16} aria-hidden="true" />
                  )}
                  Confirm Delete
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(true)}
                disabled={isLoading}
                className="p-2.5 rounded-lg bg-[var(--bg-tertiary)] hover:bg-[var(--bg-error)] text-industrial-muted hover:text-[var(--color-error)] border border-[var(--border-subtle)] transition-colors disabled:opacity-50"
                title="Delete credential"
              >
                <Trash2 size={18} aria-hidden="true" />
              </button>
            )
          )}
          {!showDeleteConfirm && (
            <>
              <button
                type="button"
                onClick={onClose}
                disabled={isLoading}
                className="flex-1 px-4 py-2.5 rounded-lg border border-[var(--border-default)] text-sm font-medium text-industrial hover:bg-[var(--hover-overlay)] transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                onClick={handleSubmit}
                disabled={isLoading}
                className="flex-1 px-4 py-2.5 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-[var(--color-neutral-900)] text-sm font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  <>
                    <div className="w-4 h-4 rounded-full border-2 border-[var(--color-neutral-900)] border-t-transparent animate-spin" />
                    Saving...
                  </>
                ) : existingCredential ? (
                  'Update Credentials'
                ) : (
                  'Connect'
                )}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
