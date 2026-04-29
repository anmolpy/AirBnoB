import { Link, Navigate, Route, Routes } from "react-router-dom";

import AdminLogin from "./pages/AdminLogin";
import GuestBooking from "./pages/GuestBooking";
import GuestCheckin from "./pages/GuestCheckin";
import StaffDashboard from "./pages/StaffDashboard";
import Navbar from "./components/navbar";

function Home() {
  return (
    <main style={styles.page}>
      <section style={styles.hero}>
        

        <div style={styles.heroGrid}>
          <div style={styles.heroCopy}>
            <p style={styles.eyebrow}>Guest checkout first</p>
            <h1 style={styles.title}>A booking flow built around minimal data and clear roles.</h1>
           

            <div style={styles.actions}>
              <Link to="/book" style={styles.primaryAction}>
                Book a room
              </Link>
              <Link to="/guest" style={styles.secondaryAction}>
                Booking status
              </Link>
            </div>
          </div>

          <aside style={styles.panel}>
            <p style={styles.panelLabel}>Quick entry points</p>
            <div style={styles.linkGrid}>
              <Link to="/staff" style={styles.linkCard}>
                <strong>Staff dashboard</strong>
                <span>Manage reservations, availability, and staff accounts.</span>
              </Link>
              <Link to="/login" style={styles.linkCard}>
                <strong>Staff login</strong>
                <span>Authenticate with the HttpOnly cookie session.</span>
              </Link>
              <Link to="/guest" style={styles.linkCard}>
                <strong>Booking Status</strong>
                <span>Verify the QR token and load the stay summary.</span>
              </Link>
              <Link to="/book" style={styles.linkCard}>
                <strong>Book a room</strong>
                <span>Reserve a stay and receive the guest token up front.</span>
              </Link>
            </div>
          </aside>
        </div>
      </section>

      <section style={styles.featureStrip}>
        <article style={styles.featureCard}>
          <p style={styles.featureTitle}>Cookie auth</p>
          <p style={styles.featureText}>JWTs stay in HttpOnly cookies, not localStorage.</p>
        </article>
        <article style={styles.featureCard}>
          <p style={styles.featureTitle}>Role separation</p>
          <p style={styles.featureText}>Admin, front desk, and guest flows stay isolated.</p>
        </article>
        <article style={styles.featureCard}>
          <p style={styles.featureTitle}>Minimal PII</p>
          <p style={styles.featureText}>Guest data is only present for the active stay window.</p>
        </article>
      </section>
    </main>
  );
}

export default function App() {
  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/book" element={<GuestBooking />} />
        <Route path="/guest/book" element={<GuestBooking />} />
        <Route path="/login" element={<AdminLogin redirectTo="/staff" />} />
        <Route path="/staff" element={<StaffDashboard loginPath="/login" />} />
        <Route path="/guest" element={<GuestCheckin />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    padding: "32px",
    color: "#0f2a10",
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  },
  hero: {
    maxWidth: "1120px",
    margin: "0 auto",
    padding: "8px 0 24px",
  },  
  brandRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "16px",
    marginBottom: "28px",
    color: "#c5ff50",
  },
 
  heroGrid: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1.3fr) minmax(280px, 0.9fr)",
    gap: "24px",
    alignItems: "stretch",
  },
  heroCopy: {
    borderRadius: "28px",
    padding: "40px",
    background: "#e8ffdd",
    color: "#07260a",
  },
  eyebrow: {
    margin: 0,
    fontSize: "12px",
    fontWeight: 700,
    letterSpacing: "0.18em",
    textTransform: "uppercase",
    color: "#ffffff",
  },
  title: {
    margin: "14px 0 0",
    maxWidth: "14ch",
    fontSize: "clamp(40px, 5vw, 72px)",
    lineHeight: 0.96,
    letterSpacing: "-0.04em",
  },
  
  actions: {
    display: "flex",
    flexWrap: "wrap",
    gap: "14px",
    marginTop: "28px",
  },
  primaryAction: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    minHeight: "48px",
    padding: "0 18px",
    borderRadius: "14px",
    background: "#a7fb6f",
    color: "#092009",
    fontWeight: 800,
    textDecoration: "none",
  },
  secondaryAction: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    minHeight: "48px",
    padding: "0 18px",
    borderRadius: "14px",
    background: "rgba(232, 255, 226, 0.92)",
    color: "#08300b",
    border: "1px solid rgba(47, 111, 18, 0.12)",
    fontWeight: 700,
    textDecoration: "none",
  },
  panel: {
    borderRadius: "28px",
    padding: "28px",
    background: "#f7fff3",
    border: "1px solid rgba(47, 111, 18, 0.08)",
  },
  panelLabel: {
    margin: 0,
    fontSize: "12px",
    fontWeight: 700,
    letterSpacing: "0.16em",
    textTransform: "uppercase",
    color: "#3f6210",
  },
  linkGrid: {
    display: "grid",
    gap: "12px",
    marginTop: "18px",
  },
  linkCard: {
    display: "grid",
    gap: "6px",
    padding: "16px 18px",
    borderRadius: "18px",
    background: "#ffffff",
    border: "1px solid #e2e8f0",
    color: "#111827",
    textDecoration: "none",
  },
  featureStrip: {
    maxWidth: "1120px",
    margin: "22px auto 0",
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
    gap: "16px",
  },
  featureCard: {
    padding: "18px 20px",
    borderRadius: "20px",
    background: "rgba(232, 255, 226, 0.95)",
    border: "1px solid rgba(47, 111, 18, 0.08)",
  },
  featureTitle: {
    margin: 0,
    fontSize: "14px",
    fontWeight: 800,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "#0f3b0b",
  },
  featureText: {
    margin: "8px 0 0",
    color: "#475569",
    lineHeight: 1.6,
  },
};