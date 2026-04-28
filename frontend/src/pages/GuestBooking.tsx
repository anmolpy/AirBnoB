import { useMemo, useState, type CSSProperties, type FormEvent } from "react";

import { isApiError, reservationsApi, type GuestBookingResponse } from "../api";

type GuestBookingProps = {
  onNavigate?: (path: string) => void;
};

type BookingForm = {
  room_id: string;
  check_in: string;
  check_out: string;
  guest_name: string;
  guest_email: string;
};

const EMPTY_FORM: BookingForm = {
  room_id: "",
  check_in: "",
  check_out: "",
  guest_name: "",
  guest_email: "",
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

export default function GuestBooking({ onNavigate }: GuestBookingProps) {
  const [copied, setCopied] = useState(false);

  async function copyToken(token: string) {
    try {
      await navigator.clipboard.writeText(token);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback for older browsers
      const el = document.createElement("textarea");
      el.value = token;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  const [form, setForm] = useState<BookingForm>(EMPTY_FORM);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<GuestBookingResponse | null>(null);

  const canSubmit =
    form.room_id.trim().length > 0 &&
    form.check_in.length > 0 &&
    form.check_out.length > 0 &&
    !isSubmitting;

  const stayWindow = useMemo(() => {
    if (!success) {
      return null;
    }

    const { reservation } = success;
    return `${formatDate(reservation.check_in)} - ${formatDate(reservation.check_out)}`;
  }, [success]);

  function updateForm(key: keyof BookingForm, value: string) {
    setForm((current) => ({
      ...current,
      [key]: value,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await reservationsApi.guestBook({
        room_id: Number(form.room_id),
        check_in: form.check_in,
        check_out: form.check_out,
        guest_name: form.guest_name || undefined,
        guest_email: form.guest_email || undefined,
      });

      setSuccess(response);
      setForm(EMPTY_FORM);
    } catch (caughtError) {
      setError(friendlyError(caughtError, "We could not book that room right now."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main style={styles.page}>
      <section style={styles.hero}>
        <div style={styles.copyPanel}>
          <p style={styles.eyebrow}>Guest booking</p>
          <h1 style={styles.title}>Book your room without creating an account.</h1>
          <p style={styles.subtitle}>
            Enter your stay details once. We create a reservation, keep minimal guest
            data, and give you a token you can use later at check-in.
          </p>

          <div style={styles.noteRow}>
            <div style={styles.noteCard}>
              <strong style={styles.noteTitle}>No account</strong>
              <span style={styles.noteText}>Guests do not need usernames or passwords.</span>
            </div>
            <div style={styles.noteCard}>
              <strong style={styles.noteTitle}>Token later</strong>
              <span style={styles.noteText}>Your booking token unlocks the guest check-in flow.</span>
            </div>
          </div>
        </div>

        <aside style={styles.formCard}>
          <form onSubmit={handleSubmit} style={styles.form}>
            <label style={styles.field}>
              <span style={styles.label}>Room number</span>
              <input
                inputMode="numeric"
                name="room_id"
                value={form.room_id}
                onChange={(event) => updateForm("room_id", event.target.value)}
                placeholder="301"
                style={styles.input}
              />
            </label>

            <div style={styles.dateGrid}>
              <label style={styles.field}>
                <span style={styles.label}>Check-in</span>
                <input
                  name="check_in"
                  type="date"
                  value={form.check_in}
                  onChange={(event) => updateForm("check_in", event.target.value)}
                  style={styles.input}
                />
              </label>

              <label style={styles.field}>
                <span style={styles.label}>Check-out</span>
                <input
                  name="check_out"
                  type="date"
                  value={form.check_out}
                  onChange={(event) => updateForm("check_out", event.target.value)}
                  style={styles.input}
                />
              </label>
            </div>

            <label style={styles.field}>
              <span style={styles.label}>Full name</span>
              <input
                autoComplete="name"
                name="guest_name"
                value={form.guest_name}
                onChange={(event) => updateForm("guest_name", event.target.value)}
                placeholder="Taylor Guest"
                style={styles.input}
              />
            </label>

            <label style={styles.field}>
              <span style={styles.label}>Email address</span>
              <input
                autoComplete="email"
                name="guest_email"
                type="email"
                value={form.guest_email}
                onChange={(event) => updateForm("guest_email", event.target.value)}
                placeholder="taylor@example.com"
                style={styles.input}
              />
            </label>

            <button type="submit" disabled={!canSubmit} style={styles.button}>
              {isSubmitting ? "Booking…" : "Book room"}
            </button>

            {error ? <p style={styles.error}>{error}</p> : null}
          </form>
        </aside>
      </section>

      <section style={styles.resultGrid}>
        <article style={styles.resultCard}>
          <h2 style={styles.sectionTitle}>What happens next</h2>
          <ol style={styles.steps}>
            <li>We create your reservation and a unique guest token.</li>
            <li>Keep the token for your stay or scan it at check-in.</li>
            <li>After checkout, guest PII is purged from the system.</li>
          </ol>
          <button type="button" onClick={() => navigate("/guest", onNavigate)} style={styles.linkButton}>
            Already booked? Go to check-in
          </button>
        </article>

        <article style={styles.resultCard}>
          <h2 style={styles.sectionTitle}>Booking confirmation</h2>

          {success ? (
            <div style={styles.confirmation}>
              <p style={styles.confirmationMessage}>{success.message}</p>
              <div style={styles.confirmationRow}>
                <span style={styles.confirmationLabel}>Reservation</span>
                <strong>#{success.reservation.id}</strong>
              </div>
              <div style={styles.confirmationRow}>
                <span style={styles.confirmationLabel}>Room</span>
                <strong>{success.reservation.room_id}</strong>
              </div>
              <div style={styles.confirmationRow}>
                <span style={styles.confirmationLabel}>Stay</span>
                <strong>{stayWindow}</strong>
              </div>
              <div style={styles.tokenBox}>
                <span style={styles.confirmationLabel}>Guest token</span>
                <div style={styles.tokenWarning}>
                  ⚠️ <strong>Save this token — you will need it to view your booking status.</strong> It will not be shown again.
                </div>
                <code style={styles.tokenCode}>{success.guest_token}</code>
                <button
                  type="button"
                  onClick={() => void copyToken(success.guest_token)}
                  style={styles.copyButton}
                >
                  {copied ? "✓ Copied!" : "Copy token"}
                </button>
              </div>
            </div>
          ) : (
            <p style={styles.placeholder}>
              Your confirmation and guest token will appear here after booking.
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
      "radial-gradient(circle at top left, rgba(217, 119, 6, 0.16), transparent 30%), radial-gradient(circle at top right, rgba(15, 23, 42, 0.12), transparent 24%), linear-gradient(180deg, #0f172a 0%, #111827 44%, #f8fafc 44%, #f8fafc 100%)",
    color: "#111827",
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  },
  hero: {
    maxWidth: "1140px",
    margin: "0 auto",
    display: "grid",
    gridTemplateColumns: "minmax(0, 1.1fr) minmax(320px, 0.9fr)",
    gap: "24px",
    alignItems: "start",
  },
  copyPanel: {
    padding: "12px 0 0",
    color: "#f8fafc",
  },
  eyebrow: {
    margin: 0,
    fontSize: "12px",
    fontWeight: 800,
    letterSpacing: "0.18em",
    textTransform: "uppercase",
    color: "#f59e0b",
  },
  title: {
    margin: "14px 0 0",
    maxWidth: "14ch",
    fontSize: "clamp(40px, 5vw, 72px)",
    lineHeight: 0.96,
    letterSpacing: "-0.04em",
  },
  subtitle: {
    margin: "18px 0 0",
    maxWidth: "58ch",
    fontSize: "17px",
    lineHeight: 1.7,
    color: "#cbd5e1",
  },
  noteRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
    gap: "14px",
    marginTop: "28px",
  },
  noteCard: {
    padding: "18px 18px 16px",
    borderRadius: "18px",
    background: "rgba(255, 255, 255, 0.08)",
    border: "1px solid rgba(255, 255, 255, 0.12)",
  },
  noteTitle: {
    display: "block",
    marginBottom: "6px",
    fontSize: "14px",
    color: "#fff",
  },
  noteText: {
    color: "#cbd5e1",
    lineHeight: 1.5,
    fontSize: "14px",
  },
  formCard: {
    background: "rgba(255, 255, 255, 0.96)",
    borderRadius: "28px",
    padding: "28px",
    border: "1px solid rgba(148, 163, 184, 0.18)",
    boxShadow: "0 28px 64px rgba(15, 23, 42, 0.18)",
  },
  form: {
    display: "grid",
    gap: "16px",
  },
  field: {
    display: "grid",
    gap: "8px",
  },
  label: {
    fontSize: "13px",
    fontWeight: 700,
    color: "#374151",
  },
  input: {
    minHeight: "46px",
    borderRadius: "14px",
    border: "1px solid #d1d5db",
    padding: "0 14px",
    background: "#fff",
    fontSize: "15px",
    boxSizing: "border-box",
  },
  dateGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: "12px",
  },
  button: {
    minHeight: "48px",
    borderRadius: "14px",
    border: "none",
    background: "#111827",
    color: "#fff",
    fontWeight: 800,
    cursor: "pointer",
  },
  error: {
    margin: 0,
    padding: "12px 14px",
    borderRadius: "14px",
    background: "#fef2f2",
    color: "#991b1b",
    border: "1px solid #fecaca",
  },
  resultGrid: {
    maxWidth: "1140px",
    margin: "24px auto 0",
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
    gap: "20px",
  },
  resultCard: {
    padding: "24px",
    borderRadius: "24px",
    background: "rgba(255, 255, 255, 0.94)",
    border: "1px solid rgba(148, 163, 184, 0.18)",
    boxShadow: "0 18px 42px rgba(15, 23, 42, 0.08)",
  },
  sectionTitle: {
    margin: "0 0 16px",
    fontSize: "20px",
    lineHeight: 1.2,
  },
  steps: {
    margin: 0,
    paddingLeft: "18px",
    display: "grid",
    gap: "10px",
    color: "#4b5563",
    lineHeight: 1.6,
  },
  linkButton: {
    marginTop: "18px",
    minHeight: "44px",
    padding: "0 16px",
    borderRadius: "12px",
    border: "1px solid #d1d5db",
    background: "#fff",
    color: "#111827",
    fontWeight: 700,
    cursor: "pointer",
  },
  placeholder: {
    margin: 0,
    color: "#6b7280",
    lineHeight: 1.6,
  },
  confirmation: {
    display: "grid",
    gap: "12px",
  },
  confirmationMessage: {
    margin: 0,
    padding: "12px 14px",
    borderRadius: "14px",
    background: "#ecfdf5",
    color: "#065f46",
    border: "1px solid #a7f3d0",
    fontWeight: 600,
  },
  confirmationRow: {
    display: "flex",
    justifyContent: "space-between",
    gap: "16px",
    alignItems: "baseline",
    paddingBottom: "8px",
    borderBottom: "1px solid #e5e7eb",
  },
  confirmationLabel: {
    fontSize: "12px",
    fontWeight: 700,
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    color: "#6b7280",
  },
  tokenBox: {
    display: "grid",
    gap: "8px",
    marginTop: "4px",
  },
  tokenWarning: {
    padding: "12px 14px",
    borderRadius: "12px",
    background: "#fffbeb",
    border: "1px solid #fcd34d",
    color: "#92400e",
    fontSize: "13px",
    lineHeight: 1.5,
  },
  copyButton: {
    minHeight: "40px",
    borderRadius: "12px",
    border: "1px solid #d1d5db",
    background: "#f8fafc",
    color: "#111827",
    fontSize: "14px",
    fontWeight: 700,
    cursor: "pointer",
  },
  tokenCode: {
    display: "block",
    padding: "14px",
    borderRadius: "14px",
    background: "#0f172a",
    color: "#f8fafc",
    wordBreak: "break-all",
    fontSize: "13px",
  },
};