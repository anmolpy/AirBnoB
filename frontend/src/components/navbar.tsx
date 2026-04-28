import { NavLink } from "react-router-dom";

import { useAuth } from "../auth";

export default function Navbar() {
  const { isAuthenticated, session, logout } = useAuth();

  return (
    <header style={styles.shell}>
      <div style={styles.inner}>
        <NavLink to="/" end style={styles.brandLink}>
          <span style={styles.brandMark}>AirBnoB</span>
          <span style={styles.brandText}>Privacy-first hotel booking</span>
        </NavLink>

        <nav aria-label="Primary navigation" style={styles.nav}>
          <NavLink
            to="/"
            end
            style={({ isActive }) => ({
              ...styles.navItem,
              ...(isActive ? styles.navItemActive : null),
            })}
          >
            Home
          </NavLink>

          <NavLink
            to="/book"
            style={({ isActive }) => ({
              ...styles.navItem,
              ...(isActive ? styles.navItemActive : null),
            })}
          >
            Book a room
          </NavLink>

          {!isAuthenticated && (
            <NavLink
              to="/login"
              style={({ isActive }) => ({
                ...styles.navItem,
                ...(isActive ? styles.navItemActive : null),
              })}
            >
              Staff login
            </NavLink>
          )}

          {isAuthenticated && (
            <NavLink
              to="/staff"
              style={({ isActive }) => ({
                ...styles.navItem,
                ...(isActive ? styles.navItemActive : null),
              })}
            >
              Staff dashboard
            </NavLink>
          )}
        </nav>

        <div style={styles.authBox}>
          {isAuthenticated && session ? (
            <>
              <div style={styles.sessionInfo}>
                <span style={styles.sessionLabel}>Signed in</span>
                <strong style={styles.sessionName}>{session.full_name}</strong>
                <span style={styles.sessionRole}>{session.role}</span>
              </div>
              <button type="button" onClick={() => void logout()} style={styles.logoutButton}>
                Sign out
              </button>
            </>
          ) : (
            <span style={styles.signedOut}>Staff sign-in available</span>
          )}
        </div>
      </div>
    </header>
  );
}

const styles: Record<string, React.CSSProperties> = {
  shell: {
    position: "sticky",
    top: 0,
    zIndex: 50,
    padding: "14px 20px",
    backdropFilter: "blur(16px)",
    background: "rgba(8, 17, 31, 0.84)",
    borderBottom: "1px solid rgba(148, 163, 184, 0.18)",
  },
  inner: {
    maxWidth: "1180px",
    margin: "0 auto",
    display: "flex",
    alignItems: "center",
    gap: "16px",
    justifyContent: "space-between",
    flexWrap: "wrap",
  },
  brandLink: {
    display: "grid",
    gap: "2px",
    textDecoration: "none",
    color: "#f8fafc",
    minWidth: "fit-content",
  },
  brandMark: {
    fontSize: "13px",
    fontWeight: 900,
    letterSpacing: "0.18em",
    textTransform: "uppercase",
  },
  brandText: {
    fontSize: "12px",
    color: "#cbd5e1",
  },
  nav: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "10px",
    flexWrap: "wrap",
    flex: "1 1 420px",
  },
  navItem: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    minHeight: "38px",
    padding: "0 14px",
    borderRadius: "999px",
    color: "#e2e8f0",
    textDecoration: "none",
    fontSize: "14px",
    fontWeight: 600,
    border: "1px solid transparent",
    background: "rgba(255, 255, 255, 0.04)",
  },
  navItemActive: {
    background: "rgba(245, 158, 11, 0.18)",
    borderColor: "rgba(245, 158, 11, 0.35)",
    color: "#fff7ed",
  },
  authBox: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    marginLeft: "auto",
  },
  sessionInfo: {
    display: "grid",
    justifyItems: "end",
    lineHeight: 1.2,
  },
  sessionLabel: {
    fontSize: "11px",
    fontWeight: 700,
    letterSpacing: "0.12em",
    textTransform: "uppercase",
    color: "#cbd5e1",
  },
  sessionName: {
    fontSize: "13px",
    color: "#f8fafc",
  },
  sessionRole: {
    fontSize: "12px",
    color: "#fbbf24",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  },
  logoutButton: {
    minHeight: "38px",
    padding: "0 14px",
    borderRadius: "999px",
    border: "1px solid rgba(248, 250, 252, 0.18)",
    background: "rgba(255, 255, 255, 0.06)",
    color: "#f8fafc",
    fontSize: "14px",
    fontWeight: 700,
    cursor: "pointer",
  },
  signedOut: {
    fontSize: "13px",
    color: "#cbd5e1",
  },
};
