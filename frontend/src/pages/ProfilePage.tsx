import { AppLayout } from '../components/Layout';
import { useAuthStore } from '../stores/authStore';
import { User, Mail, Calendar } from 'lucide-react';

export function ProfilePage() {
  const { user } = useAuthStore();

  return (
    <AppLayout>
      <div className="p-6 max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold text-white mb-6">Profile</h1>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center">
              <span className="text-white text-2xl font-medium">
                {user?.first_name?.[0] || user?.email?.[0]?.toUpperCase() || 'U'}
              </span>
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white">
                {user?.first_name} {user?.last_name}
              </h2>
              <p className="text-gray-400">{user?.email}</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center gap-3 text-gray-300">
              <User size={18} className="text-gray-500" />
              <span className="text-gray-500">Name:</span>
              <span>
                {user?.first_name || 'Not set'} {user?.last_name || ''}
              </span>
            </div>

            <div className="flex items-center gap-3 text-gray-300">
              <Mail size={18} className="text-gray-500" />
              <span className="text-gray-500">Email:</span>
              <span>{user?.email}</span>
            </div>

            <div className="flex items-center gap-3 text-gray-300">
              <Calendar size={18} className="text-gray-500" />
              <span className="text-gray-500">Member since:</span>
              <span>
                {user?.created_at
                  ? new Date(user.created_at).toLocaleDateString()
                  : 'Unknown'}
              </span>
            </div>
          </div>
        </div>

        <div className="mt-6 text-sm text-gray-500">
          Profile editing coming soon.
        </div>
      </div>
    </AppLayout>
  );
}
