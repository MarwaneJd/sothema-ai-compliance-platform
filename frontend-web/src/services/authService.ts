import type { User, UserRole } from '@/types';
import { USE_MOCK } from './api';
import { mockUsers, defaultMockUser } from '@/mocks/users';

export function getMockUser(role?: UserRole): User {
  if (role) {
    return mockUsers.find((u) => u.role === role) || defaultMockUser;
  }
  return defaultMockUser;
}

export async function getCurrentUser(): Promise<User> {
  if (USE_MOCK) {
    const savedRole = localStorage.getItem('mock_role') as UserRole | null;
    return getMockUser(savedRole || undefined);
  }
  const { default: api } = await import('./api');
  const res = await api.get('/api/users/me');
  return res.data;
}
