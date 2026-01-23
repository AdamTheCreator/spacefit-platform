import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, Loader2 } from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';

const loginSchema = z.object({
  email: z.string().email('Please enter a valid email'),
  password: z.string().min(1, 'Password is required'),
});

type LoginFormData = z.infer<typeof loginSchema>;

interface LoginFormProps {
  onSuccess?: () => void;
  onSwitchToRegister?: () => void;
}

export function LoginForm({ onSuccess, onSwitchToRegister }: LoginFormProps) {
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login, error, clearError } = useAuthStore();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginFormData) => {
    setIsSubmitting(true);
    try {
      await login(data);
      onSuccess?.();
    } catch {
      // Error is handled by the store
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
      {error && (
        <div className="flex items-start gap-3 p-3 border border-[var(--color-error)] bg-[var(--color-error)]/10">
          <span className="status-indicator status-indicator-error mt-0.5" />
          <div className="flex-1">
            <p className="text-xs font-mono text-[var(--color-error)]">{error}</p>
          </div>
          <button
            type="button"
            onClick={clearError}
            className="text-[var(--color-error)] hover:opacity-70 text-xs font-mono uppercase"
          >
            Dismiss
          </button>
        </div>
      )}

      <div>
        <label htmlFor="email" className="label-technical block mb-2">
          Email address
        </label>
        <input
          {...register('email')}
          type="email"
          id="email"
          autoComplete="email"
          spellCheck={false}
          className="input-industrial"
          placeholder="you@company.com…"
        />
        {errors.email && (
          <p className="mt-1 text-xs font-mono text-[var(--color-error)]">{errors.email.message}</p>
        )}
      </div>

      <div>
        <label htmlFor="password" className="label-technical block mb-2">
          Password
        </label>
        <div className="relative">
          <input
            {...register('password')}
            type={showPassword ? 'text' : 'password'}
            id="password"
            autoComplete="current-password"
            className="input-industrial pr-12"
            placeholder="Enter your password…"
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-industrial-muted hover:text-industrial-secondary"
          >
            {showPassword ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
          </button>
        </div>
        {errors.password && (
          <p className="mt-1 text-xs font-mono text-[var(--color-error)]">{errors.password.message}</p>
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
            Authenticating...
          </>
        ) : (
          'Sign in'
        )}
      </button>

      <p className="text-center text-xs font-mono text-industrial-muted">
        No account?{' '}
        <button
          type="button"
          onClick={onSwitchToRegister}
          className="text-[var(--accent)] hover:underline uppercase tracking-wide"
        >
          Register
        </button>
      </p>
    </form>
  );
}
