import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link } from 'react-router-dom';
import { Loader2, Mail, ArrowLeft } from 'lucide-react';
import api from '../lib/axios';

const forgotPasswordSchema = z.object({
  email: z.string().email('Please enter a valid email'),
});

type ForgotPasswordFormData = z.infer<typeof forgotPasswordSchema>;

export function ForgotPasswordPage() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotPasswordFormData>({
    resolver: zodResolver(forgotPasswordSchema),
  });

  const onSubmit = async (data: ForgotPasswordFormData) => {
    setIsSubmitting(true);
    try {
      await api.post('/auth/forgot-password', { email: data.email });
    } catch {
      // Always show success to prevent email enumeration
    } finally {
      setIsSubmitting(false);
      setIsSubmitted(true);
    }
  };

  return (
    <div className="min-h-screen bg-industrial flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-[var(--bg-secondary)] border border-[var(--border-color)] p-8">
          {!isSubmitted ? (
            <>
              <div className="mb-6">
                <h1 className="text-xl font-semibold text-industrial mb-2">
                  Forgot your password?
                </h1>
                <p className="text-sm text-industrial-muted">
                  Enter your email address and we'll send you a link to reset your password.
                </p>
              </div>

              <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
                <div>
                  <label htmlFor="email" className="text-sm font-medium text-industrial block mb-2">
                    Email address
                  </label>
                  <input
                    {...register('email')}
                    type="email"
                    id="email"
                    autoComplete="email"
                    spellCheck={false}
                    className="input-industrial"
                    placeholder="you@company.com"
                  />
                  {errors.email && (
                    <p className="mt-2 text-sm text-[var(--color-error)]">{errors.email.message}</p>
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
                      Sending...
                    </>
                  ) : (
                    'Send reset link'
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
          ) : (
            <div className="text-center">
              <div className="w-12 h-12 bg-[var(--accent)]/10 rounded-full flex items-center justify-center mx-auto mb-4">
                <Mail className="w-6 h-6 text-[var(--accent)]" />
              </div>
              <h1 className="text-xl font-semibold text-industrial mb-2">
                Check your email
              </h1>
              <p className="text-sm text-industrial-muted mb-6">
                If an account exists with that email, we've sent a password reset link. Please check your inbox.
              </p>
              <Link
                to="/login"
                className="flex items-center justify-center gap-2 text-sm text-[var(--accent)] hover:text-[var(--accent-hover)] transition-colors"
              >
                <ArrowLeft size={16} />
                Back to login
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
