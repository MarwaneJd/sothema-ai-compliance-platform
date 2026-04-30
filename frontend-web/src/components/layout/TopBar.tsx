import { useLocation } from 'react-router-dom';
import { Bell, LogOut } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { Badge } from '@/components/ui/Badge';

const routeLabels: Record<string, string> = {
  '': 'Dashboard',
  documents: 'Documents',
  compliance: 'Compliance',
  chat: 'Ask AI',
  audit: 'Audit Logs',
  settings: 'Settings',
};

export function TopBar() {
  const location = useLocation();
  const { user, logout } = useAuth();

  const segments = location.pathname.split('/').filter(Boolean);
  const breadcrumbs = [
    { label: 'Home', path: '/' },
    ...segments.map((seg, i) => ({
      label: routeLabels[seg] || seg,
      path: '/' + segments.slice(0, i + 1).join('/'),
    })),
  ];

  const initials = user?.displayName
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  return (
    <header className="h-16 glass-panel sticky top-0 z-30 mx-6 mt-4 flex items-center justify-between px-6 border-b-0">
      {/* Breadcrumbs */}
      <nav className="flex items-center text-sm font-medium text-slate-400">
        {breadcrumbs.map((crumb, i) => (
          <span key={crumb.path} className="flex items-center">
            {i > 0 && <span className="mx-2 text-slate-300">/</span>}
            <span className={i === breadcrumbs.length - 1 ? 'text-sothema-primary' : 'hover:text-slate-600 transition-colors cursor-pointer'}>
              {crumb.label}
            </span>
          </span>
        ))}
      </nav>

      {/* Right side */}
      <div className="flex items-center gap-5">
        <button className="relative text-slate-400 hover:text-sothema-primary transition-colors">
          <Bell className="h-5 w-5" />
          <span className="absolute -top-1 -right-1 w-4 h-4 bg-score-critical text-white text-[10px] font-bold rounded-full flex items-center justify-center shadow-sm">
            3
          </span>
        </button>

        <div className="flex items-center gap-3 pl-5 border-l border-slate-200">
          <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-sothema-primary to-sothema-cyan text-white flex items-center justify-center text-xs font-semibold shadow-md border-2 border-white">
            {initials}
          </div>
          <div className="hidden sm:block">
            <p className="text-sm font-semibold text-sothema-dark leading-tight">{user?.displayName}</p>
            <Badge variant="role">{user?.role || 'Viewer'}</Badge>
          </div>
          <button
            onClick={logout}
            title="Sign out"
            className="ml-2 text-slate-400 hover:text-red-600 transition-colors"
          >
            <LogOut className="h-5 w-5" />
          </button>
        </div>
      </div>
    </header>
  );
}
