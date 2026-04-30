import { LogOut } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { useAuth } from '@/hooks/useAuth';

export default function Settings() {
  const { user, logout } = useAuth();

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

      {/* Session */}
      <Card>
        <h2 className="text-lg font-semibold text-sothema-dark mb-4">Session</h2>
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">Sign out of your account on this device.</p>
          <Button variant="danger" onClick={logout}>
            <LogOut className="h-4 w-4 mr-2" />
            Sign out
          </Button>
        </div>
      </Card>
    </div>
  );
}
