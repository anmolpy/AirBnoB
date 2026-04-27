import { useEffect, type PropsWithChildren, type ReactNode } from "react";

import type { StaffRole } from "../api";
import { useAuth } from "../auth";

type RoleGuardProps = PropsWithChildren<{
  allow: StaffRole | StaffRole[];
  loginPath?: string;
  fallbackPath?: string;
  loadingFallback?: ReactNode;
  unauthorizedFallback?: ReactNode;
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

export default function RoleGuard({
  children,
  allow,
  loginPath = "/login",
  fallbackPath = "/staff",
  loadingFallback = <div>Checking your permissions...</div>,
  unauthorizedFallback = <div>Redirecting to a permitted page...</div>,
  onNavigate,
}: RoleGuardProps) {
  const { status, session, isAuthenticated, refreshSession } = useAuth();
  const allowedRoles = Array.isArray(allow) ? allow : [allow];
  const isAuthorized =
    isAuthenticated &&
    session !== null &&
    allowedRoles.includes(session.role);

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
      return;
    }

    if (status === "authenticated" && !isAuthorized) {
      navigate(fallbackPath, onNavigate);
    }
  }, [fallbackPath, isAuthorized, loginPath, onNavigate, status]);

  if (status === "loading") {
    return <>{loadingFallback}</>;
  }

  if (!isAuthenticated || !isAuthorized) {
    return <>{unauthorizedFallback}</>;
  }

  return <>{children}</>;
}
