import { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import api from '../lib/axios';

type VerifyState = 'loading' | 'success' | 'error';

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const [state, setState] = useState<VerifyState>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    const token = searchParams.get('token');

    if (!token) {
      setState('error');
      setErrorMessage('No verification token provided');
      return;
    }

    const verifyEmail = async () => {
      try {
        await api.post('/auth/verify-email', { token });
        setState('success');
      } catch (error: unknown) {
        setState('error');
        if (error && typeof error === 'object' && 'response' in error) {
          const axiosError = error as { response?: { data?: { detail?: string } } };
          setErrorMessage(axiosError.response?.data?.detail || 'Verification failed');
        } else {
          setErrorMessage('Verification failed');
        }
      }
    };

    verifyEmail();
  }, [searchParams]);

  return (
    <div className="min-h-screen bg-industrial flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-[var(--bg-secondary)] border border-[var(--border-color)] p-8">
          {state === 'loading' && (
            <div className="text-center">
              <Loader2 className="w-12 h-12 text-[var(--accent)] animate-spin mx-auto mb-4" />
              <h1 className="text-xl font-semibold text-industrial mb-2">
                Verifying your email...
              </h1>
              <p className="text-sm text-industrial-muted">
                Please wait while we verify your email address.
              </p>
            </div>
          )}

          {state === 'success' && (
            <div className="text-center">
              <CheckCircle className="w-12 h-12 text-[var(--color-success)] mx-auto mb-4" />
              <h1 className="text-xl font-semibold text-industrial mb-2">
                Email verified!
              </h1>
              <p className="text-sm text-industrial-muted mb-6">
                Your email has been verified successfully. You can now sign in to your account.
              </p>
              <Link
                to="/login"
                className="btn-industrial-primary inline-flex items-center justify-center py-3 px-6"
              >
                Go to Login
              </Link>
            </div>
          )}

          {state === 'error' && (
            <div className="text-center">
              <XCircle className="w-12 h-12 text-[var(--color-error)] mx-auto mb-4" />
              <h1 className="text-xl font-semibold text-industrial mb-2">
                Verification failed
              </h1>
              <p className="text-sm text-industrial-muted mb-6">
                {errorMessage}
              </p>
              <Link
                to="/login"
                className="btn-industrial-secondary inline-flex items-center justify-center py-3 px-6"
              >
                Go to Login
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
