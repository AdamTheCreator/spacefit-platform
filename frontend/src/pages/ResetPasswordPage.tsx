import { useState } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, Loader2, CheckCircle, XCircle, ArrowLeft } from 'lucide-react';
import api from '../lib/axios';

const resetPasswordSchema = z
  .object({
    new_password: z
      .string()
      .min(8, 'Password must be at least 8 characters')
      .regex(/[A-Z]/, 'Password must contain at least one uppercase letter')
      .regex(/[a-z]/, 'Password must contain at least one lowercase letter')
      .regex(/[0-9]/, 'Password must contain at least one number'),
    confirm_password: z.string(),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Passwords don't match",
    path: ['confirm_password'],
  });

type ResetPasswordFormData = z.infer<typeof resetPasswordSchema>;

type ResetState = 'form' | 'success' | 'error';

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [state, setState] = useState<ResetState>('form');
  const [errorMessage, setErrorMessage] = useState('');

  const token = searchParams.get('token');

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetPasswordFormData>({
    resolver: zodResolver(resetPasswordSchema),
  });

  const onSubmit = async (data: ResetPasswordFormData) => {
    if (!token) {
      setState('error');
      setErrorMessage('No reset token provided');
      return;
    }

    setIsSubmitting(true);
    try {
      await api.post('/auth/reset-password', {
        token,
        new_password: data.new_password,
      });
      setState('success');
      setTimeout(() => {
        navigate('/login');
      }, 2000);
    } catch (error: unknown) {
      setState('error');
      if (error && typeof error === 'object' && 'response' in error) {
        const axiosError = error as { response?: { data?: { detail?: string } } };
        setErrorMessage(axiosError.response?.data?.detail || 'Password reset failed');
      } else {
        setErrorMessage('Password reset failed');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen bg-industrial flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          <div className="bg-[var(--bg-secondary)] border border-[var(--border-color)] p-8 text-center">
            <XCircle className="w-12 h-12 text-[var(--color-error)] mx-auto mb-4" />
            <h1 className="text-xl font-semibold text-industrial mb-2">
              Invalid reset link
            </h1>
            <p className="text-sm text-industrial-muted mb-6">
              No reset token was provided. Please request a new password reset.
            </p>
            <Link
              to="/forgot-password"
              className="btn-industrial-secondary inline-flex items-center justify-center py-3 px-6"
            >
              Request new reset link
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-industrial flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-[var(--bg-secondary)] border border-[var(--border-color)] p-8">
          {state === 'form' && (
            <>
              <div className="mb-6">
                <h1 className="text-xl font-semibold text-industrial mb-2">
                  Reset your password
                </h1>
                <p className="text-sm text-industrial-muted">
                  Enter your new password below.
                </p>
              </div>

              <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
                <div>
                  <label htmlFor="new_password" className="text-sm font-medium text-industrial block mb-2">
                    New password
                  </label>
                  <div className="relative">
                    <input
                      {...register('new_password')}
                      type={showPassword ? 'text' : 'password'}
                      id="new_password"
                      autoComplete="new-password"
                      className="input-industrial pr-12"
                      placeholder="Create a strong password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-md text-industrial-muted hover:text-industrial transition-colors"
                    >
                      {showPassword ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
                    </button>
                  </div>
                  {errors.new_password && (
                    <p className="mt-2 text-sm text-[var(--color-error)]">{errors.new_password.message}</p>
                  )}
                </div>

                <div>
                  <label htmlFor="confirm_password" className="text-sm font-medium text-industrial block mb-2">
                    Confirm password
                  </label>
                  <input
                    {...register('confirm_password')}
                    type="password"
                    id="confirm_password"
                    autoComplete="new-password"
                    className="input-industrial"
                    placeholder="Confirm your password"
                  />
                  {errors.confirm_password && (
                    <p className="mt-2 text-sm text-[var(--color-error)]">{errors.confirm_password.message}</p>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="btn-industrial-primary w-full py-3"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                      Resetting...
                    </>
                  ) : (
                    'Reset password'
                  )}
                </button>

                <Link
                  to="/login"
                  className="flex items-center justify-center gap-2 text-sm text-industrial-muted hover:text-industrial transition-colors"
                >
                  <ArrowLeft size={16} />
                  Back to login
                </Link>
              </form>
            </>
          )}

          {state === 'success' && (
            <div className="text-center">
              <CheckCircle className="w-12 h-12 text-[var(--color-success)] mx-auto mb-4" />
              <h1 className="text-xl font-semibold text-industrial mb-2">
                Password reset!
              </h1>
              <p className="text-sm text-industrial-muted">
                Your password has been reset successfully. Redirecting to login...
              </p>
            </div>
          )}

          {state === 'error' && (
            <div className="text-center">
              <XCircle className="w-12 h-12 text-[var(--color-error)] mx-auto mb-4" />
              <h1 className="text-xl font-semibold text-industrial mb-2">
                Reset failed
              </h1>
              <p className="text-sm text-industrial-muted mb-6">
                {errorMessage}
              </p>
              <Link
                to="/forgot-password"
                className="btn-industrial-secondary inline-flex items-center justify-center py-3 px-6"
              >
                Request new reset link
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
