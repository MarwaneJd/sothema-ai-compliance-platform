import { RouterProvider } from 'react-router-dom';
import { AuthProvider } from '@/context/AuthContext';
import { SidebarProvider } from '@/context/SidebarContext';
import { router } from '@/router';

export default function App() {
  return (
    <AuthProvider>
      <SidebarProvider>
        <RouterProvider router={router} />
      </SidebarProvider>
    </AuthProvider>
  );
}
