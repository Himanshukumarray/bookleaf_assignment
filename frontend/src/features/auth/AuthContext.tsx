import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { fetchMe, login as loginRequest } from "../../api/auth";
import { setUnauthorizedHandler, tokenStore } from "../../api/client";
import type { User } from "../../types";

export interface AuthState {
  user: User | null;
  /** true while a stored token is being validated on first load */
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
}

export const AuthContext = createContext<AuthState | null>(null);

/** Focused auth state only; all server data lives in TanStack Query. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(() => tokenStore.get() !== null);

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    setUnauthorizedHandler(logout); // any 401 from the API ends the session
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  useEffect(() => {
    if (!tokenStore.get()) return;
    fetchMe()
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const response = await loginRequest(email, password);
    tokenStore.set(response.access_token);
    setUser(response.user);
    return response.user;
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
