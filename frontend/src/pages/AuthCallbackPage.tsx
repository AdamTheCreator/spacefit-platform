import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import api from '../lib/axios';

export function AuthCallbackPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { checkAuth } = useAuthStore();

  useEffect(() => {
    const finish = () =>
      checkAuth().then(() => navigate('/dashboard', { replace: true }));

    // Preferred path: single-use code exchanged for tokens (no tokens in URL).
    const code = searchParams.get('code');
    if (code) {
      api
        .post('/auth/oauth/exchange', { code })
        .then((res) => {
          localStorage.setItem('access_token', res.data.access_token);
          localStorage.setItem('refresh_token', res.data.refresh_token);
          return finish();
        })
        .catch(() => navigate('/login?error=oauth_exchange_failed', { replace: true }));
      return;
    }

    // Legacy fallback: tokens passed directly in the URL.
    const accessToken = searchParams.get('access_token');
    const refreshToken = searchParams.get('refresh_token');
    if (accessToken && refreshToken) {
      localStorage.setItem('access_token', accessToken);
      localStorage.setItem('refresh_token', refreshToken);
      finish();
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
