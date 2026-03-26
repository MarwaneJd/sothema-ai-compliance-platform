import type { User } from '@/types';

export const mockUsers: User[] = [
  {
    id: 'u-001',
    entraObjectId: 'entra-001',
    displayName: 'Amina Benali',
    email: 'a.benali@sothema.com',
    role: 'Admin',
    createdAt: '2024-01-15T08:00:00Z',
  },
  {
    id: 'u-002',
    entraObjectId: 'entra-002',
    displayName: 'Youssef El Fassi',
    email: 'y.elfassi@sothema.com',
    role: 'Analyst',
    createdAt: '2024-02-01T09:00:00Z',
  },
  {
    id: 'u-003',
    entraObjectId: 'entra-003',
    displayName: 'Sara Tazi',
    email: 's.tazi@sothema.com',
    role: 'Viewer',
    createdAt: '2024-03-10T10:00:00Z',
  },
];

export const defaultMockUser = mockUsers[1]; // Analyst by default
