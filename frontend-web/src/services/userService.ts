import type { User } from '@/types';
import api, { USE_MOCK } from './api';
import { defaultMockUser } from '@/mocks/users';

export async function getProfile(): Promise<User> {
  if (USE_MOCK) {
    return defaultMockUser;
  }
  const res = await api.get('/api/users/me');
  return res.data;
}
