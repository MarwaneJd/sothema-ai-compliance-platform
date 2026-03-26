import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { useAuth } from '@/hooks/useAuth';
import type { UserRole } from '@/types';

const roles: UserRole[] = ['Admin', 'Analyst', 'Viewer'];

export default function Settings() {
  const { user, switchRole } = useAuth();

  if (!user) return null;

  const initials = user.displayName
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-sothema-dark">Settings</h1>

      {/* Profile */}
      <Card>
        <h2 className="text-lg font-semibold text-sothema-dark mb-4">Profile</h2>
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-sothema-navy text-white flex items-center justify-center text-xl font-bold">
            {initials}
          </div>
          <div>
            <p className="text-lg font-semibold text-sothema-dark">{user.displayName}</p>
            <p className="text-sm text-gray-500">{user.email}</p>
            <Badge variant="role" className="mt-1">{user.role}</Badge>
          </div>
        </div>
      </Card>

      {/* Role Switcher (Dev Mode) */}
      <Card>
        <div className="flex items-center gap-2 mb-4">
          <h2 className="text-lg font-semibold text-sothema-dark">Role Switcher</h2>
          <span className="px-2 py-0.5 bg-yellow-100 text-yellow-800 text-[10px] font-bold rounded uppercase">Dev</span>
        </div>
        <p className="text-sm text-gray-500 mb-4">
          Switch between roles to test different permission levels. This is only available in mock mode.
        </p>
        <div className="flex gap-3">
          {roles.map((role) => (
            <Button
              key={role}
              variant={user.role === role ? 'primary' : 'secondary'}
              size="sm"
              onClick={() => switchRole(role)}
            >
              {role}
            </Button>
          ))}
        </div>
      </Card>

      {/* App Info */}
      <Card>
        <h2 className="text-lg font-semibold text-sothema-dark mb-4">Application Info</h2>
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-gray-500">API Base URL</dt>
            <dd className="text-sothema-dark font-mono text-xs mt-1">{import.meta.env.VITE_API_BASE_URL || 'N/A'}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Mock Mode</dt>
            <dd className="mt-1"><Badge>{import.meta.env.VITE_USE_MOCK !== 'false' ? 'Enabled' : 'Disabled'}</Badge></dd>
          </div>
          <div>
            <dt className="text-gray-500">Version</dt>
            <dd className="text-sothema-dark font-mono text-xs mt-1">0.1.0</dd>
          </div>
        </dl>
      </Card>
    </div>
  );
}
