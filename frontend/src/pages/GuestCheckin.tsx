import { useEffect, useMemo, useState, type CSSProperties } from "react";

import { guestAuthApi, isApiError, type GuestSession, type Reservation } from "../api";

type GuestCheckinProps = {
  onNavigate?: (path: string) => void;
};

type GuestState = {
  session: GuestSession | null;
  reservation: Reservation | null;
};

const EMPTY_GUEST_STATE: GuestState = {
  session: null,
  reservation: null,
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

function formatDate(dateString: string): string {
  const date = new Date(dateString);

  if (Number.isNaN(date.getTime())) {
    return dateString;
  }

  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function friendlyError(error: unknown, fallback: string): string {
  return isApiError(error) ? error.message : fallback;
}

function statusTone(status: Reservation["status"]): CSSProperties {
  switch (status) {
    case "pending":
      return { background: "#fef3c7", color: "#92400e" };
    case "active":
      return { background: "#dcfce7", color: "#166534" };
    case "checked_out":
      return { background: "#e0f2fe", color: "#075985" };
    case "cancelled":
      return { background: "#fee2e2", color: "#991b1b" };
    default:
      return {};
  }
}

export default function GuestCheckin({ onNavigate }: GuestCheckinProps) {
  const [state, setState] = useState<GuestState>(EMPTY_GUEST_STATE);
  const [isHydrating, setIsHydrating] = useState(true);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isAuthenticated = state.session !== null;

  async function loadGuestSession() {
    try {
      const session = await guestAuthApi.me();
      const reservation = await guestAuthApi.reservation();

      setState({ session, reservation });
      setError(null);
    } catch (caughtError) {
      const apiError = isApiError(caughtError) ? caughtError : null;

      if (apiError?.status === 401 || apiError?.status === 403) {
        setState(EMPTY_GUEST_STATE);
        setError(null);
        return;
      }

      setState(EMPTY_GUEST_STATE);
      setError(friendlyError(caughtError, "We could not load your guest session."));
    }
  }

  useEffect(() => {
    let isMounted = true;

    async function hydrate() {
      try {
        await loadGuestSession();
      } finally {
        if (isMounted) {
          setIsHydrating(false);
        }
      }
    }

    void hydrate();

    return () => {
      isMounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stayWindow = useMemo(() => {
    if (!state.session) {
      return null;
    }

    return `${formatDate(state.session.check_in)} - ${formatDate(state.session.check_out)}`;
  }, [state.session]);

  async function handleLogout() {
    setIsLoggingOut(true);

    try {
      await guestAuthApi.logout();
    } finally {
      setState(EMPTY_GUEST_STATE);
      setError(null);
      setIsLoggingOut(false);
    }
  }

  if (isHydrating) {
    return <div>Loading your guest session…</div>;
  }

  return (
    <main style={styles.page}>
      <section style={styles.heroCard}>
        <header style={styles.header}>
          <p style={styles.eyebrow}>AirBnoB Guest Access</p>
          <h1 style={styles.title}>Your stay summary</h1>
          <p style={styles.subtitle}>
            Check-in is handled by front desk staff. Your stay details are shown below once your session is active.
          </p>
        </header>
        {error ? (
          <div style={styles.messageStack}>
            <p style={styles.errorMessage}>{error}</p>
          </div>
        ) : null}
      </section>

      <section style={styles.detailGrid}>
        <article style={styles.panel}>
          <h2 style={styles.panelTitle}>Guest session</h2>

          {isAuthenticated && state.session ? (
            <dl style={styles.definitionList}>
              <div style={styles.definitionItem}>
                <dt style={styles.term}>Room</dt>
                <dd style={styles.definition}>{state.session.room_id}</dd>
              </div>
              <div style={styles.definitionItem}>
                <dt style={styles.term}>Stay window</dt>
                <dd style={styles.definition}>{stayWindow}</dd>
              </div>
              <div style={styles.definitionItem}>
                <dt style={styles.term}>Status</dt>
                <dd style={styles.definition}>{state.session.message}</dd>
              </div>
            </dl>
          ) : (
            <p style={styles.mutedText}>
              Your room and stay details will appear here once staff have checked you in.
            </p>
          )}

          {isAuthenticated ? (
            <button type="button" onClick={() => void handleLogout()} disabled={isLoggingOut} style={styles.secondaryButton}>
              {isLoggingOut ? "Ending session…" : "End guest session"}
            </button>
          ) : null}
        </article>

        <article style={styles.panel}>
          <h2 style={styles.panelTitle}>Reservation</h2>

          {state.reservation ? (
            <div style={styles.reservationCard}>
              <div style={styles.reservationHeader}>
                <p style={styles.reservationNumber}>Reservation #{state.reservation.id}</p>
                <span style={{ ...styles.statusPill, ...statusTone(state.reservation.status) }}>
                  {state.reservation.status}
                </span>
              </div>

              <dl style={styles.definitionList}>
                <div style={styles.definitionItem}>
                  <dt style={styles.term}>Room</dt>
                  <dd style={styles.definition}>{state.reservation.room_id}</dd>
                </div>
                <div style={styles.definitionItem}>
                  <dt style={styles.term}>Dates</dt>
                  <dd style={styles.definition}>
                    {formatDate(state.reservation.check_in)} - {formatDate(state.reservation.check_out)}
                  </dd>
                </div>
                <div style={styles.definitionItem}>
                  <dt style={styles.term}>Nights</dt>
                  <dd style={styles.definition}>{state.reservation.nights}</dd>
                </div>
                <div style={styles.definitionItem}>
                  <dt style={styles.term}>Guest</dt>
                  <dd style={styles.definition}>{state.reservation.guest_name ?? "Guest"}</dd>
                </div>
                <div style={styles.definitionItem}>
                  <dt style={styles.term}>Email</dt>
                  <dd style={styles.definition}>{state.reservation.guest_email ?? "Not stored"}</dd>
                </div>
              </dl>
            </div>
          ) : (
            <p style={styles.mutedText}>
              Once verified, your reservation summary will appear here.
            </p>
          )}
        </article>
      </section>
    </main>
  );
}

const styles: Record<string, CSSProperties> = {
  page: {
    minHeight: "100vh",
    padding: "32px 24px 48px",
    background:
      "radial-gradient(circle at top left, rgba(217, 119, 6, 0.18), transparent 34%), linear-gradient(180deg, #111827 0%, #1f2937 50%, #f9fafb 50%, #f9fafb 100%)",
    color: "#111827",
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  },
  heroCard: {
    maxWidth: "960px",
    margin: "0 auto",
    background: "rgba(255, 255, 255, 0.96)",
    border: "1px solid rgba(255, 255, 255, 0.24)",
    borderRadius: "24px",
    padding: "32px",
    boxShadow: "0 30px 80px rgba(17, 24, 39, 0.18)",
    backdropFilter: "blur(16px)",
  },
  header: {
    display: "grid",
    gap: "10px",
    marginBottom: "24px",
  },
  eyebrow: {
    margin: 0,
    fontSize: "12px",
    fontWeight: 700,
    letterSpacing: "0.16em",
    textTransform: "uppercase",
    color: "#92400e",
  },
  title: {
    margin: 0,
    fontSize: "clamp(30px, 5vw, 52px)",
    lineHeight: 1,
    color: "#111827",
  },
  subtitle: {
    margin: 0,
    maxWidth: "68ch",
    fontSize: "15px",
    lineHeight: 1.6,
    color: "#4b5563",
  },
  form: {
    display: "grid",
    gap: "16px",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    alignItems: "end",
  },
  field: {
    display: "grid",
    gap: "8px",
  },
  label: {
    fontSize: "14px",
    fontWeight: 600,
    color: "#374151",
  },
  input: {
    width: "100%",
    minHeight: "48px",
    borderRadius: "14px",
    border: "1px solid #d1d5db",
    padding: "0 16px",
    fontSize: "15px",
    outline: "none",
    boxSizing: "border-box",
    background: "#fff",
  },
  button: {
    minHeight: "48px",
    padding: "0 18px",
    borderRadius: "14px",
    border: "none",
    background: "#111827",
    color: "#ffffff",
    fontSize: "14px",
    fontWeight: 700,
    cursor: "pointer",
  },
  messageStack: {
    display: "grid",
    gap: "10px",
    marginTop: "20px",
  },
  errorMessage: {
    margin: 0,
    padding: "14px 16px",
    borderRadius: "14px",
    background: "#fef2f2",
    color: "#991b1b",
    border: "1px solid #fecaca",
  },
  successMessage: {
    margin: 0,
    padding: "14px 16px",
    borderRadius: "14px",
    background: "#ecfdf5",
    color: "#065f46",
    border: "1px solid #a7f3d0",
  },
  detailGrid: {
    maxWidth: "960px",
    margin: "24px auto 0",
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
    gap: "20px",
  },
  panel: {
    background: "rgba(255, 255, 255, 0.92)",
    borderRadius: "20px",
    padding: "24px",
    border: "1px solid rgba(17, 24, 39, 0.08)",
    boxShadow: "0 18px 40px rgba(17, 24, 39, 0.08)",
  },
  panelTitle: {
    margin: "0 0 18px",
    fontSize: "20px",
    lineHeight: 1.2,
  },
  mutedText: {
    margin: 0,
    color: "#6b7280",
    lineHeight: 1.6,
  },
  definitionList: {
    display: "grid",
    gap: "14px",
    margin: 0,
  },
  definitionItem: {
    display: "grid",
    gap: "4px",
  },
  term: {
    fontSize: "12px",
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "#6b7280",
  },
  definition: {
    margin: 0,
    fontSize: "15px",
    lineHeight: 1.5,
    color: "#111827",
  },
  secondaryButton: {
    marginTop: "18px",
    minHeight: "44px",
    padding: "0 16px",
    borderRadius: "12px",
    border: "1px solid #d1d5db",
    background: "#fff",
    color: "#111827",
    fontSize: "14px",
    fontWeight: 600,
    cursor: "pointer",
  },
  reservationCard: {
    display: "grid",
    gap: "16px",
  },
  reservationHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "12px",
  },
  reservationNumber: {
    margin: 0,
    fontSize: "16px",
    fontWeight: 700,
    color: "#111827",
  },
  statusPill: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    minHeight: "28px",
    padding: "0 12px",
    borderRadius: "999px",
    fontSize: "12px",
    fontWeight: 700,
    textTransform: "capitalize",
  },
};
