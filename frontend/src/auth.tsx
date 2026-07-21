import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { authApi } from "./api";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated" | "setup";
export type AuthMode = "normal" | "demo" | "dev";

type AuthContextValue = {
  status: AuthStatus;
  mode: AuthMode;
  login: (password: string) => Promise<boolean>;
  setup: (password: string) => Promise<{ recovery_key?: string } | null>;
  demo: () => Promise<boolean>;
  recover: (recoveryKey: string, newPassword: string) => Promise<boolean>;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [mode, setMode] = useState<AuthMode>("normal");

  const refresh = useCallback(async () => {
    const s = await authApi.status();
    if (s.dev_open) {
      setMode("dev");
      setStatus("authenticated");
      return;
    }
    if (s.needs_setup) {
      setStatus("setup");
      return;
    }
    const ok = await authApi.checkSession();
    setStatus(ok ? "authenticated" : "unauthenticated");
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = useCallback(
    async (password: string) => {
      const ok = await authApi.login(password);
      if (ok) {
        setMode("normal");
        await refresh();
      }
      return ok;
    },
    [refresh],
  );

  const setup = useCallback(
    async (password: string) => {
      const res = await authApi.setup(password);
      if (!res) return null;
      setMode("normal");
      await refresh();
      return res;
    },
    [refresh],
  );

  const demo = useCallback(async () => {
    const ok = await authApi.demo();
    if (ok) {
      setMode("demo");
      setStatus("authenticated");
    }
    return ok;
  }, []);

  const recover = useCallback(
    async (recoveryKey: string, newPassword: string) => {
      const ok = await authApi.recover(recoveryKey, newPassword);
      if (ok) await refresh();
      return ok;
    },
    [refresh],
  );

  const value = useMemo(
    () => ({ status, mode, login, setup, demo, recover, refresh }),
    [status, mode, login, setup, demo, recover, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
