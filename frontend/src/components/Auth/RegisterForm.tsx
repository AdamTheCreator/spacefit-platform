import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, Loader2 } from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';

const registerSchema = z
  .object({
    first_name: z.string().min(1, 'First name is required'),
    last_name: z.string().min(1, 'Last name is required'),
    email: z.string().email('Please enter a valid email'),
    password: z
      .string()
      .min(8, 'Password must be at least 8 characters')
      .regex(/[A-Z]/, 'Password must contain at least one uppercase letter')
      .regex(/[a-z]/, 'Password must contain at least one lowercase letter')
      .regex(/[0-9]/, 'Password must contain at least one number'),
    confirm_password: z.string(),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Passwords don't match",
    path: ['confirm_password'],
  });

type RegisterFormData = z.infer<typeof registerSchema>;

interface RegisterFormProps {
  onSuccess?: () => void;
  onSwitchToLogin?: () => void;
}

export function RegisterForm({ onSuccess, onSwitchToLogin }: RegisterFormProps) {
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { register: registerUser, error, clearError } = useAuthStore();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (data: RegisterFormData) => {
    setIsSubmitting(true);
    try {
      await registerUser({
        email: data.email,
        password: data.password,
        first_name: data.first_name,
        last_name: data.last_name,
      });
      onSuccess?.();
    } catch {
      // Error is handled by the store
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
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

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="first_name" className="label-technical block mb-2">
            First name
          </label>
          <input
            {...register('first_name')}
            type="text"
            id="first_name"
            autoComplete="given-name"
            className="input-industrial"
            placeholder="John…"
          />
          {errors.first_name && (
            <p className="mt-1 text-xs font-mono text-[var(--color-error)]">{errors.first_name.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="last_name" className="label-technical block mb-2">
            Last name
          </label>
          <input
            {...register('last_name')}
            type="text"
            id="last_name"
            autoComplete="family-name"
            className="input-industrial"
            placeholder="Doe…"
          />
          {errors.last_name && (
            <p className="mt-1 text-xs font-mono text-[var(--color-error)]">{errors.last_name.message}</p>
          )}
        </div>
      </div>

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
            autoComplete="new-password"
            className="input-industrial pr-12"
            placeholder="Create a strong password…"
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

      <div>
        <label htmlFor="confirm_password" className="label-technical block mb-2">
          Confirm password
        </label>
        <input
          {...register('confirm_password')}
          type="password"
          id="confirm_password"
          autoComplete="new-password"
          className="input-industrial"
          placeholder="Confirm your password…"
        />
        {errors.confirm_password && (
          <p className="mt-1 text-xs font-mono text-[var(--color-error)]">{errors.confirm_password.message}</p>
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
            Creating account...
          </>
        ) : (
          'Create account'
        )}
      </button>

      <p className="text-center text-xs font-mono text-industrial-muted">
        Already registered?{' '}
        <button
          type="button"
          onClick={onSwitchToLogin}
          className="text-[var(--accent)] hover:underline uppercase tracking-wide"
        >
          Sign in
        </button>
      </p>
    </form>
  );
}
