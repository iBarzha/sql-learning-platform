import apiClient from './client';
import type { AuthResponse, User } from '@/types';

export interface LoginData {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
  password_confirm: string;
  first_name?: string;
  last_name?: string;
}

export interface ChangePasswordData {
  old_password: string;
  new_password: string;
  new_password_confirm: string;
}

export interface SetPasswordData {
  new_password: string;
  new_password_confirm: string;
}

export interface InviteAcceptData {
  token: string;
  password: string;
  password_confirm: string;
  first_name?: string;
  last_name?: string;
}

export interface InviteCheckResponse {
  valid: boolean;
  email?: string;
  role?: string;
  course?: string;
  detail?: string;
}

export const authApi = {
  login: async (data: LoginData): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>('/auth/login/', data);
    return response.data;
  },

  register: async (data: RegisterData): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>('/auth/register/', data);
    return response.data;
  },

  logout: async (refresh?: string): Promise<void> => {
    await apiClient.post('/auth/logout/', { refresh });
  },

  getMe: async (): Promise<User> => {
    const response = await apiClient.get<User>('/auth/me/');
    return response.data;
  },

  updateMe: async (data: Partial<User>): Promise<User> => {
    const response = await apiClient.patch<User>('/auth/me/', data);
    return response.data;
  },

  changePassword: async (data: ChangePasswordData): Promise<void> => {
    await apiClient.post('/auth/change-password/', data);
  },

  setPassword: async (data: SetPasswordData): Promise<void> => {
    await apiClient.post('/auth/set-password/', data);
  },

  acceptInvite: async (data: InviteAcceptData): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>('/auth/invite/accept/', data);
    return response.data;
  },

  checkInvite: async (token: string): Promise<InviteCheckResponse> => {
    const response = await apiClient.get<InviteCheckResponse>(`/auth/invite/check/${token}/`);
    return response.data;
  },

  refreshToken: async (refresh: string): Promise<{ access: string }> => {
    const response = await apiClient.post<{ access: string }>('/auth/token/refresh/', {
      refresh,
    });
    return response.data;
  },
};

export default authApi;
