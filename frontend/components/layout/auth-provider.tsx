"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api } from "@/lib/api";
import { setAccessToken, type UserOut } from "@/lib/auth";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

type LoginResponse = { access_token: string; user: UserOut };

type AuthContextValue = {
  user: UserOut | null;
  status: AuthStatus;
  login: (email: string, password: string) => Promise<UserOut>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  useEffect(() => {
    let cancelled = false;
    api
      .post<LoginResponse>("/auth/refresh", undefined, { skipAuth: true })
      .then((data) => {
        if (cancelled) return;
        setAccessToken(data.access_token);
        setUser(data.user);
        setStatus("authenticated");
      })
      .catch(() => {
        if (cancelled) return;
        setAccessToken(null);
        setStatus("unauthenticated");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const data = await api.post<LoginResponse>("/auth/login", { email, password }, { skipAuth: true });
    setAccessToken(data.access_token);
    setUser(data.user);
    setStatus("authenticated");
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      setAccessToken(null);
      setUser(null);
      setStatus("unauthenticated");
    }
  }, []);

  return <AuthContext.Provider value={{ user, status, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
