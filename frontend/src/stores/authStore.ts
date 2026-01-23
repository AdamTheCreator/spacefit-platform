import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { AxiosError } from 'axios';
import api from '../lib/axios';
import type { User, LoginRequest, RegisterRequest, TokenResponse } from '../types/auth';

interface AuthStore {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  clearError: () => void;
  setUser: (user: User) => void;
}

function extractErrorMessage(error: unknown, defaultMsg: string): string {
  if (error instanceof AxiosError && error.response?.data) {
    const data = error.response.data;
    if (typeof data.detail === 'string') {
      return data.detail;
    }
    if (typeof data.message === 'string') {
      return data.message;
    }
  }
  if (error instanceof Error) {
    return error.message;
  }
  return defaultMsg;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      isLoading: true,
      error: null,

      login: async (data: LoginRequest) => {
        set({ isLoading: true, error: null });
        try {
          const response = await api.post<TokenResponse>('/auth/login', data);
          const { access_token, refresh_token } = response.data;

          localStorage.setItem('access_token', access_token);
          localStorage.setItem('refresh_token', refresh_token);

          try {
            const userResponse = await api.get<User>('/auth/me');
            set({
              user: userResponse.data,
              isAuthenticated: true,
              isLoading: false,
            });
          } catch (meError: unknown) {
            // /auth/me failed but tokens are valid - clear and report
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            const message = extractErrorMessage(meError, 'Failed to fetch user profile.');
            set({ error: message, isLoading: false, isAuthenticated: false, user: null });
            throw meError;
          }
        } catch (error: unknown) {
          // Only set error if not already set by inner catch
          if (get().isLoading) {
            const message = extractErrorMessage(error, 'Login failed. Please check your credentials.');
            set({ error: message, isLoading: false });
          }
          throw error;
        }
      },

      register: async (data: RegisterRequest) => {
        set({ isLoading: true, error: null });
        try {
          await api.post('/auth/register', data);

          await get().login({ email: data.email, password: data.password });
        } catch (error: unknown) {
          // Only set error if not already set by login()
          if (get().isLoading) {
            const message = extractErrorMessage(error, 'Registration failed.');
            set({ error: message, isLoading: false });
          }
          throw error;
        }
      },

      logout: async () => {
        const refreshToken = localStorage.getItem('refresh_token');

        if (refreshToken) {
          try {
            await api.post('/auth/logout', { refresh_token: refreshToken });
          } catch {
            // Ignore errors during logout
          }
        }

        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');

        set({
          user: null,
          isAuthenticated: false,
          isLoading: false,
          error: null,
        });
      },

      checkAuth: async () => {
        const token = localStorage.getItem('access_token');

        if (!token) {
          set({ isAuthenticated: false, isLoading: false, user: null });
          return;
        }

        // Only set loading if we don't already have a user (avoid flicker after login)
        if (!get().user) {
          set({ isLoading: true });
        }

        try {
          const response = await api.get<User>('/auth/me');
          set({
            user: response.data,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          set({
            user: null,
            isAuthenticated: false,
            isLoading: false,
          });
        }
      },

      clearError: () => set({ error: null }),

      setUser: (user: User) => set({ user }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
