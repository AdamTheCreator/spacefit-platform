import { useNavigate, useLocation } from 'react-router-dom';
import { LoginForm } from '../components/Auth/LoginForm';
import { SocialLoginButtons } from '../components/Auth/SocialLoginButtons';

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as { from?: Location })?.from?.pathname || '/';

  const handleSuccess = () => {
    navigate(from, { replace: true });
  };

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Welcome back</h1>
          <p className="text-gray-400">Sign in to your SpaceFit AI account</p>
        </div>

        <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-8">
          <SocialLoginButtons />

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-700" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-gray-800/50 text-gray-400">or continue with email</span>
            </div>
          </div>

          <LoginForm
            onSuccess={handleSuccess}
            onSwitchToRegister={() => navigate('/register')}
          />
        </div>
      </div>
    </div>
  );
}
