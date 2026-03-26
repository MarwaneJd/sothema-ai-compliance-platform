import type { ReactNode } from 'react';
import type { UserRole } from '@/types';
import { useAuth } from '@/hooks/useAuth';
import { Card } from '@/components/ui/Card';
import { ShieldX } from 'lucide-react';

interface RoleGuardProps {
  role: UserRole;
  children: ReactNode;
}

export function RoleGuard({ role, children }: RoleGuardProps) {
  const { user } = useAuth();

  if (!user) return null;

  const roleHierarchy: Record<UserRole, number> = { Admin: 3, Analyst: 2, Viewer: 1 };

  if (roleHierarchy[user.role] < roleHierarchy[role]) {
    return (
      <div className="flex items-center justify-center py-20">
        <Card className="text-center max-w-md">
          <ShieldX className="h-12 w-12 mx-auto mb-4 text-red-400" />
          <h2 className="text-lg font-semibold text-sothema-dark mb-2">Access Denied</h2>
          <p className="text-sm text-gray-500">
            You need the <strong>{role}</strong> role to access this page. Your current role is{' '}
            <strong>{user.role}</strong>.
          </p>
        </Card>
      </div>
    );
  }

  return <>{children}</>;
}
