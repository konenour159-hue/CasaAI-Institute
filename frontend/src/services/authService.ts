import { api } from "./apiClient";
import type { TokenPair, UserPublic } from "../types/api";

export const authService = {
  register: (data: { first_name: string; last_name: string; email: string; password: string }) =>
    api.post<UserPublic>("/api/auth/register", data),

  login: (data: { email: string; password: string }) =>
    api.post<TokenPair>("/api/auth/login", data),

  refresh: (refresh_token: string) =>
    api.post<{ access_token: string; token_type: string }>("/api/auth/refresh", { refresh_token }),

  logout: () => api.post<void>("/api/auth/logout", undefined, true),

  me: () => api.get<UserPublic>("/api/auth/me", true),

  updateMe: (data: { first_name: string; last_name: string; email: string; current_password?: string }) =>
    api.patch<UserPublic>("/api/auth/me", data, true),

  changePassword: (data: { current_password: string; new_password: string }) =>
    api.post<void>("/api/auth/me/password", data, true),
};
