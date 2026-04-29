import { useEffect, useMemo, useState, type CSSProperties, type FormEvent } from "react";

import { isApiError } from "../api";
import { useAuth } from "../auth/AuthContext";

type AdminLoginProps = {
  redirectTo?: string;
  onNavigate?: (path: string) => void;
};

function navigate(path: string, onNavigate?: (path: string) => void) {
  if (onNavigate) {
    onNavigate(path);
    return;
  }
  if (typeof window !== "undefined") {
    window.location.assign(path);
  }
}

export default function AdminLogin({ redirectTo = "/staff", onNavigate }: AdminLoginProps) {
  const { login, isAuthenticated, status, clearError } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isAuthenticated) navigate(redirectTo, onNavigate);
  }, [isAuthenticated, onNavigate, redirectTo]);

  useEffect(() => { clearError(); }, [clearError]);

  const isBusy = status === "loading" || isSubmitting;
  const canSubmit = email.trim().length > 0 && password.length > 0 && !isBusy;

  const helperMessage = useMemo(() => {
    if (submitError) return submitError;
    return "Sign in with your staff credentials. Authentication is maintained with secure cookies.";
  }, [submitError]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);
    setIsSubmitting(true);
    try {
      await login({ email, password });
      navigate(redirectTo, onNavigate);
    } catch (caughtError) {
      if (isApiError(caughtError) && caughtError.status === 401) {
        setSubmitError("Incorrect email or password.");
      } else if (isApiError(caughtError)) {
        setSubmitError(caughtError.message);
      } else {
        setSubmitError("We could not sign you in. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  if (status === "loading" && !isAuthenticated) return <div>Checking your session…</div>;
  if (isAuthenticated) return <div>Redirecting to your dashboard…</div>;

  return (
    <main style={styles.page}>
      <section style={styles.card}>
        <header style={styles.header}>
          <p style={styles.eyebrow}>AirBnoB Staff</p>
          <h1 style={styles.title}>Sign in</h1>
          <p style={styles.subtitle}>{helperMessage}</p>
        </header>

        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.field}>
            <span style={styles.label}>Email</span>
            <input
              autoComplete="email"
              name="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="staff@airbnob.local"
              style={styles.input}
            />
          </label>

          <label style={styles.field}>
            <span style={styles.label}>Password</span>
            <div style={styles.passwordWrapper}>
              <input
                autoComplete="current-password"
                name="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                style={styles.passwordInput}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                style={styles.eyeButton}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </label>

          <button type="submit" disabled={!canSubmit} style={styles.button}>
            {isSubmitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}

const styles: Record<string, CSSProperties> = {
  page: {
    minHeight: "100vh",
    display: "grid",
    placeItems: "center",
    padding: "24px",
    background: "#f4fff4",
    color: "#07260a",
    fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  },
  card: {
    width: "100%",
    maxWidth: "420px",
    background: "#ffffff",
    border: "1px solid rgba(47, 111, 18, 0.06)",
    borderRadius: "8px",
    padding: "32px",
    boxShadow: "0 12px 32px rgba(17, 24, 39, 0.08)",
  },
  header: { display: "grid", gap: "8px", marginBottom: "24px" },
  eyebrow: { margin: 0, fontSize: "12px", fontWeight: 600, textTransform: "uppercase", color: "#4b5563" },
  title: { margin: 0, fontSize: "32px", lineHeight: 1.1 },
  subtitle: { margin: 0, fontSize: "14px", lineHeight: 1.5, color: "#6b7280" },
  form: { display: "grid", gap: "16px" },
  field: { display: "grid", gap: "8px" },
  label: { fontSize: "14px", fontWeight: 600 },
  input: {
    width: "100%",
    minHeight: "44px",
    borderRadius: "8px",
    border: "1px solid #d1d5db",
    padding: "0 14px",
    fontSize: "14px",
    outline: "none",
    boxSizing: "border-box",
  },
  passwordWrapper: {
    position: "relative",
    display: "flex",
    alignItems: "center",
  },
  passwordInput: {
    width: "100%",
    minHeight: "44px",
    borderRadius: "8px",
    border: "1px solid #d1d5db",
    padding: "0 60px 0 14px",
    fontSize: "14px",
    outline: "none",
    boxSizing: "border-box",
  },
  eyeButton: {
    position: "absolute",
    right: "12px",
    background: "none",
    border: "none",
    color: "#6b7280",
    fontSize: "13px",
    fontWeight: 600,
    cursor: "pointer",
    padding: "0",
  },
  button: {
    minHeight: "44px",
    borderRadius: "8px",
    border: "none",
    background: "#111827",
    color: "#ffffff",
    fontSize: "14px",
    fontWeight: 600,
    cursor: "pointer",
  },
};
