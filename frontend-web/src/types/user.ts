export type UserRole = 'Admin' | 'Analyst' | 'Viewer';

export interface User {
  id: string;
  entraObjectId: string;
  displayName: string;
  email: string;
  role: UserRole;
  createdAt: string;
}
