import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';

export function AuthCallbackPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { checkAuth } = useAuthStore();

  useEffect(() => {
    const accessToken = searchParams.get('access_token');
    const refreshToken = searchParams.get('refresh_token');

    if (accessToken && refreshToken) {
      localStorage.setItem('access_token', accessToken);
      localStorage.setItem('refresh_token', refreshToken);

      checkAuth().then(() => {
        navigate('/dashboard', { replace: true });
      });
    } else {
      navigate('/login', { replace: true });
    }
  }, [searchParams, navigate, checkAuth]);

  return (
    <div className="min-h-screen bg-industrial flex items-center justify-center dark">
      <div className="flex flex-col items-center gap-4">
        <div className="relative w-10 h-10">
          <div className="w-10 h-10 border border-industrial" />
          <div className="absolute inset-0 border-t border-[var(--accent)] animate-spin" />
        </div>
        <p className="label-technical">Completing sign in...</p>
      </div>
    </div>
  );
}
