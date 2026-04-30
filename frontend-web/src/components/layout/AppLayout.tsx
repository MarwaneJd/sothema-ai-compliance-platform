import { useContext } from 'react';
import { Outlet } from 'react-router-dom';
import { SidebarContext } from '@/context/SidebarContext';
import { useAuth } from '@/hooks/useAuth';
import Login from '@/pages/Login';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export function AppLayout() {
  const { collapsed } = useContext(SidebarContext);
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <Login />;
  }

  return (
    <div className="min-h-screen bg-sothema-bg">
      <Sidebar />
      <div className={`transition-all duration-300 ${collapsed ? 'ml-16' : 'ml-60'}`}>
        <TopBar />
        <main className="p-6 pt-8 max-w-[1600px] mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
