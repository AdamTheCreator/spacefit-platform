import { useState, useEffect, useCallback } from 'react';
import { X, Loader2, Eye, EyeOff, Shield, Monitor, Trash2, BarChart3, Building2 } from 'lucide-react';
import type { SiteConfig, Credential } from '../../types/credentials';

// Map site IDs to Lucide icons
const SITE_ICONS: Record<string, React.ReactNode> = {
  siteusa: <BarChart3 size={20} className="text-blue-400" />,
  costar: <Building2 size={20} className="text-purple-400" />,
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
      className="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-gray-800 rounded-xl border border-gray-700 shadow-xl w-full max-w-md mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gray-700 rounded-lg flex items-center justify-center">
              {SITE_ICONS[site.id] || <BarChart3 size={20} className="text-gray-400" />}
            </div>
            <div>
              <h2 id="modal-title" className="text-lg font-semibold text-white">
                {existingCredential ? 'Update' : 'Connect to'} {site.name}
              </h2>
              {site.is_browser_based && (
                <p className="text-xs text-purple-400 flex items-center gap-1">
                  <Monitor size={10} />
                  Browser-based connection
                </p>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close modal"
            className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-gray-700 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {displayError && (
            <div className="p-3 bg-red-900/30 border border-red-700/50 rounded-lg text-red-400 text-sm">
              {displayError}
            </div>
          )}

          <div>
            <label htmlFor="credential-username" className="block text-sm font-medium text-gray-300 mb-1">
              Email / Username
            </label>
            <input
              id="credential-username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={`Enter your ${site.name} email`}
              className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              autoComplete="username"
              disabled={isLoading}
            />
          </div>

          <div>
            <label htmlFor="credential-password" className="block text-sm font-medium text-gray-300 mb-1">
              Password
              {existingCredential && (
                <span className="text-gray-500 font-normal ml-2">
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
                className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent pr-12"
                autoComplete="current-password"
                disabled={isLoading}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
              >
                {showPassword ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
              </button>
            </div>
          </div>

          {/* Security info */}
          <div className="flex items-start gap-2 p-3 bg-gray-700/50 rounded-lg">
            <Shield size={16} className="text-green-400 mt-0.5 flex-shrink-0" aria-hidden="true" />
            <p className="text-xs text-gray-400">
              Your credentials are encrypted using AES-256 and stored securely.
              They are only used to access your {site.name} account on your behalf.
            </p>
          </div>

          {/* Browser automation info */}
          {site.is_browser_based && (
            <div className="flex items-start gap-2 p-3 bg-purple-900/20 border border-purple-700/30 rounded-lg">
              <Monitor size={16} className="text-purple-400 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-gray-400">
                This connection uses browser automation. Queries will take
                approximately {site.typical_duration_seconds} seconds. You'll see
                progress updates during analysis.
              </p>
            </div>
          )}
        </form>

        {/* Footer */}
        <div className="flex gap-3 p-4 border-t border-gray-700">
          {existingCredential && onDelete && (
            showDeleteConfirm ? (
              <div className="flex gap-2 flex-1">
                <button
                  type="button"
                  onClick={() => setShowDeleteConfirm(false)}
                  disabled={isLoading}
                  className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors disabled:opacity-50 text-sm"
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
                  className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center justify-center gap-2 text-sm"
                >
                  {isLoading ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                  Confirm Delete
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(true)}
                disabled={isLoading}
                className="p-2 bg-gray-700 hover:bg-red-600/20 text-gray-400 hover:text-red-400 rounded-lg transition-colors disabled:opacity-50"
                title="Delete credential"
              >
                <Trash2 size={18} />
              </button>
            )
          )}
          {!showDeleteConfirm && (
            <>
              <button
                type="button"
                onClick={onClose}
                disabled={isLoading}
                className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                onClick={handleSubmit}
                disabled={isLoading}
                className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
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
