"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { toast } from "sonner";

import { api, ApiError, SESSION_ENDED_EVENT } from "@/lib/api";
import { setAccessToken, type UserOut } from "@/lib/auth";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

type LoginResponse = { access_token: string; user: UserOut };

type AuthContextValue = {
  user: UserOut | null;
  status: AuthStatus;
  login: (username: string, password: string) => Promise<UserOut>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const SESSION_CHECK_MS = 60_000;
// Restoring the session on page load: a free-tier API can take ~a minute to wake up.
const RESTORE_ATTEMPTS = 6;
const RESTORE_RETRY_MS = 10_000;

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  useEffect(() => {
    let cancelled = false;
    // Only a 401 means there's no session. Other failures (the API waking up from sleep, a
    // timeout) are retried for a while rather than sending the user back to the login page.
    const restore = async () => {
      for (let attempt = 1; ; attempt++) {
        try {
          return await api.post<LoginResponse>("/auth/refresh", undefined, { skipAuth: true });
        } catch (error) {
          const noSession = error instanceof ApiError && error.status === 401;
          if (noSession || attempt >= RESTORE_ATTEMPTS || cancelled) throw error;
          await new Promise((resolve) => setTimeout(resolve, RESTORE_RETRY_MS));
        }
      }
    };
    restore()
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

  // Ends this tab's session as soon as the server has ended it (password reset, admin
  // sign-out): on any request that can't renew the session, and by checking every minute and
  // when the tab regains focus, so an idle page is signed out too.
  useEffect(() => {
    if (status !== "authenticated") return;
    const endSession = () => {
      setAccessToken(null);
      setUser(null);
      setStatus("unauthenticated");
      toast.info("Your session has ended. Please sign in again.");
    };
    const check = () => {
      if (document.visibilityState === "visible") api.get("/auth/me").catch(() => {});
    };
    window.addEventListener(SESSION_ENDED_EVENT, endSession);
    document.addEventListener("visibilitychange", check);
    const timer = setInterval(check, SESSION_CHECK_MS);
    return () => {
      window.removeEventListener(SESSION_ENDED_EVENT, endSession);
      document.removeEventListener("visibilitychange", check);
      clearInterval(timer);
    };
  }, [status]);

  const login = useCallback(async (username: string, password: string) => {
    const data = await api.post<LoginResponse>("/auth/login", { username, password }, { skipAuth: true });
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
