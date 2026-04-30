import { createContext, useState, useEffect, type ReactNode } from 'react';
import { useMsal, useIsAuthenticated } from '@azure/msal-react';
import type { User, UserRole } from '@/types';
import { USE_MOCK } from '@/services/api';
import { getMockUser } from '@/services/authService';
import { loginRequest, msalEnabled } from '@/auth/msalConfig';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  login: () => Promise<void>;
  logout: () => void;
  switchRole: (role: UserRole) => void;
}

export const AuthContext = createContext<AuthContextType>({
  user: null,
  isAuthenticated: false,
  login: async () => {},
  logout: () => {},
  switchRole: () => {},
});

const useMockAuth = USE_MOCK || !msalEnabled;

export function AuthProvider({ children }: { children: ReactNode }) {
  return useMockAuth ? (
    <MockAuthProvider>{children}</MockAuthProvider>
  ) : (
    <MsalAuthProvider>{children}</MsalAuthProvider>
  );
}

function MockAuthProvider({ children }: { children: ReactNode }) {
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

  const login = async () => {};

  return (
    <AuthContext.Provider
      value={{ user, isAuthenticated: !!user, login, logout, switchRole }}
    >
      {children}
    </AuthContext.Provider>
  );
}

function MsalAuthProvider({ children }: { children: ReactNode }) {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (!isAuthenticated || accounts.length === 0) {
      setUser(null);
      localStorage.removeItem('auth_token');
      return;
    }

    const account = accounts[0];
    let cancelled = false;

    instance
      .acquireTokenSilent({ ...loginRequest, account })
      .then((result) => {
        if (cancelled) return;
        localStorage.setItem('auth_token', result.accessToken);
        const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
        return fetch(`${baseUrl}/api/users/me`, {
          headers: { Authorization: `Bearer ${result.accessToken}` },
        });
      })
      .then((res) => (res ? res.json() : null))
      .then((profile) => {
        if (!cancelled) setUser(profile);
      })
      .catch((err) => {
        if (!cancelled) {
          console.error('Failed to load profile', err);
          setUser(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, accounts, instance]);

  const login = async () => {
    try {
      await instance.loginRedirect(loginRequest);
    } catch (err) {
      console.error('Login failed', err);
    }
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    instance.logoutRedirect();
    setUser(null);
  };

  const switchRole = () => {
    console.warn('switchRole is disabled outside mock mode. Roles come from the backend.');
  };

  return (
    <AuthContext.Provider
      value={{ user, isAuthenticated: isAuthenticated && !!user, login, logout, switchRole }}
    >
      {children}
    </AuthContext.Provider>
  );
}
