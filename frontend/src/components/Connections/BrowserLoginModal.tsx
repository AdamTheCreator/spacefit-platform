import { useState, useEffect, useCallback, useRef } from 'react';
import { X, Monitor, Shield, CheckCircle2, XCircle, Loader2, ExternalLink, RefreshCw } from 'lucide-react';
import type { SiteConfig, Credential } from '../../types/credentials';
import api from '../../lib/axios';

interface LoginStatus {
  status: string;
  message: string;
  progress_pct: number;
  timestamp: string;
}

interface BrowserLoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  site: SiteConfig | null;
  existingCredential: Credential | null;
  onSuccess: () => void;
}

const STATUS_MESSAGES: Record<string, { icon: React.ReactNode; color: string }> = {
  initializing: { icon: <Loader2 className="animate-spin" size={20} />, color: 'text-[var(--accent)]' },
  browser_opening: { icon: <Monitor size={20} />, color: 'text-[var(--accent)]' },
  navigating: { icon: <Loader2 className="animate-spin" size={20} />, color: 'text-[var(--accent)]' },
  waiting_for_login: { icon: <Monitor size={20} />, color: 'text-amber-500' },
  login_detected: { icon: <CheckCircle2 size={20} />, color: 'text-[var(--color-success)]' },
  saving_session: { icon: <Loader2 className="animate-spin" size={20} />, color: 'text-[var(--accent)]' },
  success: { icon: <CheckCircle2 size={20} />, color: 'text-[var(--color-success)]' },
  failed: { icon: <XCircle size={20} />, color: 'text-[var(--color-error)]' },
  cancelled: { icon: <XCircle size={20} />, color: 'text-industrial-muted' },
  timeout: { icon: <XCircle size={20} />, color: 'text-[var(--color-error)]' },
};

export function BrowserLoginModal({
  isOpen,
  onClose,
  site,
  existingCredential,
  onSuccess,
}: BrowserLoginModalProps) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<LoginStatus | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Reset state when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      setSessionId(null);
      setStatus(null);
      setIsStarting(false);
      setIsComplete(false);
      setError(null);
    } else {
      // Cleanup WebSocket on close
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    }
  }, [isOpen]);

  // Handle Escape key
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape' && isOpen && !isStarting) {
      onClose();
    }
  }, [isOpen, isStarting, onClose]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const startBrowserLogin = async () => {
    const token = localStorage.getItem('access_token');
    if (!site || !token) return;

    setIsStarting(true);
    setError(null);
    setStatus({
      status: 'initializing',
      message: 'Preparing browser session...',
      progress_pct: 0,
      timestamp: new Date().toISOString(),
    });

    try {
      // Start the browser login session via the shared axios instance
      // (which already points at the correct backend origin)
      const { data } = await api.post<{ session_id: string; websocket_url: string }>(
        `/browser-auth/start/${site.id}`,
        { credential_id: existingCredential?.id },
      );

      setSessionId(data.session_id);

      // Build the WebSocket URL against the same backend origin that
      // axios uses (VITE_API_URL || http://localhost:8000).
      const backendOrigin = (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000';
      const wsOrigin = backendOrigin.replace(/^http/, 'ws');
      const wsUrl = `${wsOrigin}${data.websocket_url}?token=${token}`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected for browser login');
      };

      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);

        if (message.type === 'status') {
          setStatus(message.data);
        } else if (message.type === 'complete') {
          setIsComplete(true);
          if (message.data.success) {
            setStatus({
              status: 'success',
              message: message.data.message,
              progress_pct: 100,
              timestamp: new Date().toISOString(),
            });
            // Delay calling onSuccess to show success state
            setTimeout(() => {
              onSuccess();
            }, 1500);
          } else {
            setStatus({
              status: 'failed',
              message: message.data.message,
              progress_pct: 100,
              timestamp: new Date().toISOString(),
            });
          }
        } else if (message.type === 'error') {
          setError(message.data.message);
          setIsComplete(true);
        }
      };

      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        setError('Connection error. Please try again.');
        setIsComplete(true);
      };

      ws.onclose = () => {
        console.log('WebSocket closed');
        wsRef.current = null;
      };

    } catch (err: unknown) {
      // axios errors carry the server message in err.response.data.detail
      let message = 'Failed to start browser login';
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        message = axiosErr.response?.data?.detail || message;
      } else if (err instanceof Error) {
        message = err.message;
      }
      setError(message);
      setIsStarting(false);
    }
  };

  const cancelLogin = async () => {
    if (sessionId) {
      try {
        await api.post(`/browser-auth/cancel/${sessionId}`);
      } catch (err) {
        console.error('Failed to cancel login:', err);
      }
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsStarting(false);
    setIsComplete(false);
    setStatus(null);
    setSessionId(null);
  };

  if (!isOpen || !site) return null;

  const statusConfig = status ? STATUS_MESSAGES[status.status] || STATUS_MESSAGES.initializing : null;
  const isWaitingForUser = status?.status === 'waiting_for_login';
  const isSuccess = status?.status === 'success';
  const isFailed = status?.status === 'failed' || status?.status === 'timeout';

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
        onClick={() => !isStarting && onClose()}
      />

      {/* Modal */}
      <div className="relative bg-[var(--bg-elevated)] border border-[var(--border-subtle)] rounded-2xl shadow-xl w-full max-w-lg animate-scale-in">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-[var(--border-subtle)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[var(--bg-tertiary)] border border-[var(--border-subtle)] flex items-center justify-center">
              <Monitor size={20} className="text-[var(--accent)]" />
            </div>
            <div>
              <h2 id="modal-title" className="text-base font-semibold text-industrial">
                Connect to {site.name}
              </h2>
              <p className="text-xs text-[var(--accent)] flex items-center gap-1 mt-0.5">
                <Shield size={12} />
                Secure browser login
              </p>
            </div>
          </div>
          {!isStarting && (
            <button
              onClick={onClose}
              aria-label="Close modal"
              className="p-2 rounded-lg text-industrial-muted hover:text-industrial hover:bg-[var(--hover-overlay)] transition-colors"
            >
              <X size={20} />
            </button>
          )}
        </div>

        {/* Body */}
        <div className="p-5 space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-[var(--bg-error)] border border-[var(--color-error)]/20 text-sm text-[var(--color-error)]">
              {error}
            </div>
          )}

          {!isStarting ? (
            // Initial state - show explanation
            <>
              <div className="space-y-3">
                <p className="text-sm text-industrial-secondary">
                  {site.name} requires you to log in through a browser window to verify your credentials.
                  This is because they use CAPTCHA protection.
                </p>

                <div className="bg-[var(--bg-tertiary)] rounded-xl p-4 space-y-3">
                  <h3 className="text-sm font-medium text-industrial">How it works:</h3>
                  <ol className="text-sm text-industrial-secondary space-y-2">
                    <li className="flex gap-2">
                      <span className="w-5 h-5 rounded-full bg-[var(--accent)] text-[var(--color-neutral-900)] text-xs flex items-center justify-center flex-shrink-0 mt-0.5">1</span>
                      <span>A browser window will open on your screen</span>
                    </li>
                    <li className="flex gap-2">
                      <span className="w-5 h-5 rounded-full bg-[var(--accent)] text-[var(--color-neutral-900)] text-xs flex items-center justify-center flex-shrink-0 mt-0.5">2</span>
                      <span>Enter your {site.name} credentials</span>
                    </li>
                    <li className="flex gap-2">
                      <span className="w-5 h-5 rounded-full bg-[var(--accent)] text-[var(--color-neutral-900)] text-xs flex items-center justify-center flex-shrink-0 mt-0.5">3</span>
                      <span>Solve the CAPTCHA if one appears</span>
                    </li>
                    <li className="flex gap-2">
                      <span className="w-5 h-5 rounded-full bg-[var(--accent)] text-[var(--color-neutral-900)] text-xs flex items-center justify-center flex-shrink-0 mt-0.5">4</span>
                      <span>We'll automatically save your session</span>
                    </li>
                  </ol>
                </div>

                <div className="flex items-start gap-3 p-3 rounded-lg bg-[var(--bg-success)] border border-[var(--color-success)]/20">
                  <Shield size={16} className="text-[var(--color-success)] mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-industrial-secondary leading-relaxed">
                    Your session is stored securely and will be valid for 24 hours.
                    We never store your password - only the session cookies.
                  </p>
                </div>
              </div>
            </>
          ) : (
            // In-progress state - show status
            <div className="space-y-4">
              {/* Progress bar */}
              <div className="space-y-2">
                <div className="h-2 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[var(--accent)] transition-all duration-500 ease-out"
                    style={{ width: `${status?.progress_pct || 0}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-industrial-muted">
                  <span>{status?.progress_pct || 0}%</span>
                  <span>{isWaitingForUser ? 'Waiting for you...' : 'Processing...'}</span>
                </div>
              </div>

              {/* Status message */}
              <div className={`flex items-center gap-3 p-4 rounded-xl bg-[var(--bg-tertiary)] ${statusConfig?.color || ''}`}>
                {statusConfig?.icon}
                <div className="flex-1">
                  <p className="text-sm font-medium text-industrial">
                    {status?.message || 'Starting...'}
                  </p>
                  {isWaitingForUser && (
                    <p className="text-xs text-industrial-muted mt-1">
                      Complete the login in the browser window that opened
                    </p>
                  )}
                </div>
              </div>

              {/* Waiting for user indicator */}
              {isWaitingForUser && (
                <div className="flex items-center gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
                  <ExternalLink size={20} className="text-amber-500" />
                  <div>
                    <p className="text-sm font-medium text-industrial">
                      Browser window is open
                    </p>
                    <p className="text-xs text-industrial-muted mt-0.5">
                      Look for the {site.name} login page in a new browser window
                    </p>
                  </div>
                </div>
              )}

              {/* Success state */}
              {isSuccess && (
                <div className="flex items-center gap-3 p-4 rounded-xl bg-[var(--bg-success)] border border-[var(--color-success)]/20">
                  <CheckCircle2 size={20} className="text-[var(--color-success)]" />
                  <div>
                    <p className="text-sm font-medium text-[var(--color-success)]">
                      Successfully connected!
                    </p>
                    <p className="text-xs text-industrial-muted mt-0.5">
                      Your {site.name} session is now active
                    </p>
                  </div>
                </div>
              )}

              {/* Failed state */}
              {isFailed && (
                <div className="flex items-center gap-3 p-4 rounded-xl bg-[var(--bg-error)] border border-[var(--color-error)]/20">
                  <XCircle size={20} className="text-[var(--color-error)]" />
                  <div>
                    <p className="text-sm font-medium text-[var(--color-error)]">
                      Connection failed
                    </p>
                    <p className="text-xs text-industrial-muted mt-0.5">
                      {status?.message || 'Please try again'}
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex gap-3 p-5 border-t border-[var(--border-subtle)]">
          {!isStarting ? (
            <>
              <button
                type="button"
                onClick={onClose}
                className="flex-1 px-4 py-2.5 rounded-lg border border-[var(--border-default)] text-sm font-medium text-industrial hover:bg-[var(--hover-overlay)] transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={startBrowserLogin}
                className="flex-1 px-4 py-2.5 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-[var(--color-neutral-900)] text-sm font-medium transition-colors flex items-center justify-center gap-2"
              >
                <Monitor size={16} />
                Open Browser Login
              </button>
            </>
          ) : isComplete ? (
            <>
              {isFailed && (
                <button
                  type="button"
                  onClick={() => {
                    setIsStarting(false);
                    setIsComplete(false);
                    setStatus(null);
                    setError(null);
                  }}
                  className="flex-1 px-4 py-2.5 rounded-lg border border-[var(--border-default)] text-sm font-medium text-industrial hover:bg-[var(--hover-overlay)] transition-colors flex items-center justify-center gap-2"
                >
                  <RefreshCw size={16} />
                  Try Again
                </button>
              )}
              <button
                type="button"
                onClick={onClose}
                className="flex-1 px-4 py-2.5 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-[var(--color-neutral-900)] text-sm font-medium transition-colors"
              >
                {isSuccess ? 'Done' : 'Close'}
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={cancelLogin}
              className="flex-1 px-4 py-2.5 rounded-lg border border-[var(--border-default)] text-sm font-medium text-industrial hover:bg-[var(--hover-overlay)] transition-colors"
            >
              Cancel Login
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
