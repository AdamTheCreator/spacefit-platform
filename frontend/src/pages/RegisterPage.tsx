import { useNavigate } from 'react-router-dom';
import { RegisterForm } from '../components/Auth/RegisterForm';
import { SocialLoginButtons } from '../components/Auth/SocialLoginButtons';

export function RegisterPage() {
  const navigate = useNavigate();

  const handleSuccess = () => {
    navigate('/onboarding', { replace: true });
  };

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Create an account</h1>
          <p className="text-gray-400">Get started with SpaceFit AI</p>
        </div>

        <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-8">
          <SocialLoginButtons />

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-700" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-gray-800/50 text-gray-400">or register with email</span>
            </div>
          </div>

          <RegisterForm
            onSuccess={handleSuccess}
            onSwitchToLogin={() => navigate('/login')}
          />
        </div>
      </div>
    </div>
  );
}
