import { createContext, useState, useEffect, type ReactNode } from 'react';
import type { User, UserRole } from '@/types';
import { getMockUser } from '@/services/authService';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  switchRole: (role: UserRole) => void;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextType>({
  user: null,
  isAuthenticated: false,
  switchRole: () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const savedRole = localStorage.getItem('mock_role') as UserRole | null;
    setUser(getMockUser(savedRole || undefined));
  }, []);

  const switchRole = (role: UserRole) => {
    localStorage.setItem('mock_role', role);
    setUser(getMockUser(role));
  };

  const logout = () => {
    localStorage.removeItem('mock_role');
    localStorage.removeItem('auth_token');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, switchRole, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
