import axios from 'axios';
import type { PaginatedResponse } from '@/types';

export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.message || error.message || 'An error occurred';
    return Promise.reject({ message, status: error.response?.status || 500 });
  },
);

export default api;

export function paginateMock<T>(items: T[], page: number, pageSize: number): PaginatedResponse<T> {
  const start = (page - 1) * pageSize;
  const paged = items.slice(start, start + pageSize);
  return {
    items: paged,
    totalCount: items.length,
    page,
    pageSize,
    totalPages: Math.ceil(items.length / pageSize),
  };
}
