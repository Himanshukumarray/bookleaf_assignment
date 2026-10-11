import { api } from "./client";
import type { TokenResponse, User } from "../types";

export const login = async (email: string, password: string): Promise<TokenResponse> =>
  (await api.post<TokenResponse>("/auth/login", { email, password })).data;

export const fetchMe = async (): Promise<User> => (await api.get<User>("/auth/me")).data;
