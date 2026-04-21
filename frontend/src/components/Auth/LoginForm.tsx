import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link } from 'react-router-dom';
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

const inputClass =
  'w-full px-3.5 py-2.5 rounded-lg border text-sm outline-none transition-colors' +
  ' border-[#E0DFDD] bg-white text-[#1A1918] placeholder:text-[#A3A19D]' +
  ' focus:border-[#E5A840] focus:ring-1 focus:ring-[#E5A840]';

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
        <div className="flex items-start gap-3 p-4 rounded-xl border border-red-200 bg-red-50">
          <span className="w-2 h-2 rounded-full bg-red-500 mt-1.5 flex-shrink-0" />
          <p className="flex-1 text-sm text-red-600">{error}</p>
          <button type="button" onClick={clearError} className="text-red-500 hover:opacity-70 text-xs font-medium">
            Dismiss
          </button>
        </div>
      )}

      <div>
        <label htmlFor="email" className="text-sm font-medium block mb-2" style={{ color: '#1A1918' }}>
          Email address
        </label>
        <input
          {...register('email')}
          type="email"
          id="email"
          autoComplete="email"
          spellCheck={false}
          className={inputClass}
          placeholder="you@company.com"
        />
        {errors.email && (
          <p className="mt-2 text-sm text-red-500">{errors.email.message}</p>
        )}
      </div>

      <div>
        <label htmlFor="password" className="text-sm font-medium block mb-2" style={{ color: '#1A1918' }}>
          Password
        </label>
        <div className="relative">
          <input
            {...register('password')}
            type={showPassword ? 'text' : 'password'}
            id="password"
            autoComplete="current-password"
            className={`${inputClass} pr-12`}
            placeholder="Enter your password"
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-md transition-colors"
            style={{ color: '#A3A19D' }}
          >
            {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        </div>
        {errors.password && (
          <p className="mt-2 text-sm text-red-500">{errors.password.message}</p>
        )}
        <div className="mt-2 text-right">
          <Link to="/forgot-password" className="text-sm font-medium transition-colors" style={{ color: '#E5A840' }}>
            Forgot password?
          </Link>
        </div>
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full py-3 rounded-lg text-sm font-semibold text-white transition-colors flex items-center justify-center gap-2 disabled:opacity-60"
        style={{ background: '#E5A840' }}
      >
        {isSubmitting ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            Signing in...
          </>
        ) : (
          'Sign in'
        )}
      </button>

      <p className="text-center text-sm" style={{ color: '#A3A19D' }}>
        Don't have an account?{' '}
        <button type="button" onClick={onSwitchToRegister} className="font-medium transition-colors" style={{ color: '#E5A840' }}>
          Register
        </button>
      </p>
    </form>
  );
}
