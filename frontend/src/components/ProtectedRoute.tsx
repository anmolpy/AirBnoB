import { useEffect, type PropsWithChildren, type ReactNode } from "react";

import { useAuth } from "../auth";

type ProtectedRouteProps = PropsWithChildren<{
  loginPath?: string;
  loadingFallback?: ReactNode;
  redirectFallback?: ReactNode;
  onNavigate?: (path: string) => void;
}>;

function navigate(path: string, onNavigate?: (path: string) => void) {
  if (onNavigate) {
    onNavigate(path);
    return;
  }

  if (typeof window !== "undefined") {
    window.location.assign(path);
  }
}

export default function ProtectedRoute({
  children,
  loginPath = "/login",
  loadingFallback = <div>Checking your session...</div>,
  redirectFallback = <div>Redirecting to login...</div>,
  onNavigate,
}: ProtectedRouteProps) {
  const { status, isAuthenticated, refreshSession } = useAuth();

  useEffect(() => {
    if (status === "loading") {
      return;
    }

    if (!isAuthenticated) {
      void refreshSession();
    }
  }, [isAuthenticated, refreshSession, status]);

  useEffect(() => {
    if (status === "unauthenticated") {
      navigate(loginPath, onNavigate);
    }
  }, [loginPath, onNavigate, status]);

  if (status === "loading") {
    return <>{loadingFallback}</>;
  }

  if (!isAuthenticated) {
    return <>{redirectFallback}</>;
  }

  return <>{children}</>;
}
