import { AppLayout } from '../components/Layout';
import { useAuthStore } from '../stores/authStore';
import { User, Mail, Calendar } from 'lucide-react';

export function ProfilePage() {
  const { user } = useAuthStore();

  return (
    <AppLayout>
      <div className="p-6 max-w-2xl mx-auto bg-industrial min-h-full">
        <h1 className="font-mono text-lg font-bold tracking-tight text-industrial mb-6">Profile</h1>

        <div className="card-industrial">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-16 h-16 bg-[var(--accent)] flex items-center justify-center">
              <span className="text-[var(--color-industrial-900)] text-2xl font-mono font-bold">
                {user?.first_name?.[0] || user?.email?.[0]?.toUpperCase() || 'U'}
              </span>
            </div>
            <div>
              <h2 className="font-mono text-lg font-semibold text-industrial">
                {user?.first_name} {user?.last_name}
              </h2>
              <p className="font-mono text-sm text-industrial-muted">{user?.email}</p>
            </div>
          </div>

          <div className="space-y-4 pt-4 border-t border-industrial">
            <div className="flex items-center gap-3">
              <User size={16} className="text-industrial-muted" />
              <span className="label-technical w-24">Name</span>
              <span className="font-mono text-sm text-industrial">
                {user?.first_name || 'Not set'} {user?.last_name || ''}
              </span>
            </div>

            <div className="flex items-center gap-3">
              <Mail size={16} className="text-industrial-muted" />
              <span className="label-technical w-24">Email</span>
              <span className="font-mono text-sm text-industrial">{user?.email}</span>
            </div>

            <div className="flex items-center gap-3">
              <Calendar size={16} className="text-industrial-muted" />
              <span className="label-technical w-24">Member since</span>
              <span className="font-mono text-sm text-industrial">
                {user?.created_at
                  ? new Date(user.created_at).toLocaleDateString()
                  : 'Unknown'}
              </span>
            </div>
          </div>
        </div>

        <div className="mt-6 font-mono text-xs text-industrial-muted uppercase tracking-wide">
          Profile editing coming soon.
        </div>
      </div>
    </AppLayout>
  );
}
