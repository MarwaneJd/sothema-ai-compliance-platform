import { useContext } from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, FileText, ShieldCheck, MessageCircle, ScrollText, Settings, ChevronLeft, ChevronRight } from 'lucide-react';
import { SidebarContext } from '@/context/SidebarContext';
import { useAuth } from '@/hooks/useAuth';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/documents', icon: FileText, label: 'Documents' },
  { to: '/compliance', icon: ShieldCheck, label: 'Compliance' },
  { to: '/chat', icon: MessageCircle, label: 'Ask AI' },
  { to: '/audit', icon: ScrollText, label: 'Audit Logs', requiredRole: 'Admin' as const },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

export function Sidebar() {
  const { collapsed, toggle } = useContext(SidebarContext);
  const { user } = useAuth();

  return (
    <aside
      className={`fixed left-0 top-0 h-screen bg-gradient-to-b from-sothema-primary to-sothema-primary-dark text-white flex flex-col transition-all duration-300 z-40 shadow-xl ${
        collapsed ? 'w-16' : 'w-60'
      }`}
    >
      {/* Logo */}
      <div className="flex items-center h-16 px-4 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-white/20 backdrop-blur-sm rounded-lg flex items-center justify-center flex-shrink-0 shadow-inner">
            <ShieldCheck className="h-5 w-5" />
          </div>
          {!collapsed && (
            <div className="overflow-hidden">
              <span className="font-bold text-sm tracking-wide">SOTHEMA</span>
              <span className="block text-[10px] text-white/70 -mt-0.5 font-medium">Compliance AI</span>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 space-y-1.5 px-3">
        {navItems.map((item) => {
          if (item.requiredRole && user?.role !== item.requiredRole) return null;
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200 ${
                  isActive
                    ? 'bg-white/15 text-white shadow-[0_2px_10px_rgba(0,0,0,0.1)] border border-white/10 font-medium'
                    : 'text-white/70 hover:bg-white/10 hover:text-white hover:-translate-y-0.5'
                }`
              }
            >
              <Icon className="h-5 w-5 flex-shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={toggle}
        className="flex items-center justify-center h-12 border-t border-white/10 text-white/50 hover:text-white hover:bg-white/10 transition-colors"
      >
        {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
      </button>
    </aside>
  );
}
