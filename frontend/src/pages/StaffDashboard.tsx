import {
  useEffect,
  useMemo,
  useState,
  type ChangeEvent,
  type CSSProperties,
  type FormEvent,
  type ReactNode,
} from "react";

import {
  adminApi,
  isApiError,
  reservationsApi,
  type AvailabilityResponse,
  type Reservation,
  type ReservationStatus,
  type StaffSession,
} from "../api";
import { useAuth } from "../auth/AuthContext";

type StaffDashboardProps = {
  loginPath?: string;
  onNavigate?: (path: string) => void;
};

type ReservationFilters = {
  status: "" | ReservationStatus;
  roomId: string;
};

type CreateReservationForm = {
  room_id: string;
  check_in: string;
  check_out: string;
  guest_name: string;
  guest_email: string;
};

type AvailabilityForm = {
  room_id: string;
  check_in: string;
  check_out: string;
};

type StaffCreateForm = {
  email: string;
  full_name: string;
  password: string;
  role: StaffSession["role"];
};

const EMPTY_CREATE_RESERVATION_FORM: CreateReservationForm = {
  room_id: "",
  check_in: "",
  check_out: "",
  guest_name: "",
  guest_email: "",
};

const EMPTY_AVAILABILITY_FORM: AvailabilityForm = {
  room_id: "",
  check_in: "",
  check_out: "",
};

const EMPTY_STAFF_FORM: StaffCreateForm = {
  email: "",
  full_name: "",
  password: "",
  role: "front_desk",
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

function friendlyError(error: unknown, fallback: string): string {
  return isApiError(error) ? error.message : fallback;
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

function statusTone(status: ReservationStatus): CSSProperties {
  switch (status) {
    case "pending":
      return {
        background: "#fef3c7",
        color: "#92400e",
      };
    case "active":
      return {
        background: "#dcfce7",
        color: "#166534",
      };
    case "checked_out":
      return {
        background: "#e0f2fe",
        color: "#075985",
      };
    case "cancelled":
      return {
        background: "#fee2e2",
        color: "#991b1b",
      };
    default:
      return {};
  }
}

export default function StaffDashboard({
  loginPath = "/login",
  onNavigate,
}: StaffDashboardProps) {
  const { status, session, logout, refreshSession } = useAuth();
  const isAdmin = session?.role === "admin";

  const [filters, setFilters] = useState<ReservationFilters>({
    status: "",
    roomId: "",
  });
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [selectedReservationId, setSelectedReservationId] = useState<number | null>(null);
  const [selectedReservation, setSelectedReservation] = useState<Reservation | null>(null);
  const [reservationsLoading, setReservationsLoading] = useState(false);
  const [reservationsError, setReservationsError] = useState<string | null>(null);

  const [createForm, setCreateForm] = useState<CreateReservationForm>(
    EMPTY_CREATE_RESERVATION_FORM,
  );
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSuccess, setCreateSuccess] = useState<string | null>(null);
  const [createSubmitting, setCreateSubmitting] = useState(false);

  const [availabilityForm, setAvailabilityForm] = useState<AvailabilityForm>(
    EMPTY_AVAILABILITY_FORM,
  );
  const [availabilityLoading, setAvailabilityLoading] = useState(false);
  const [availabilityError, setAvailabilityError] = useState<string | null>(null);
  const [availabilityResult, setAvailabilityResult] = useState<AvailabilityResponse | null>(
    null,
  );

  const [cancelReason, setCancelReason] = useState("");
  const [reservationActionError, setReservationActionError] = useState<string | null>(null);
  const [reservationActionSuccess, setReservationActionSuccess] = useState<string | null>(
    null,
  );
  const [actionBusyKey, setActionBusyKey] = useState<string | null>(null);

  const [qrToken, setQrToken] = useState("");
  const [qrCheckinLoading, setQrCheckinLoading] = useState(false);
  const [qrCheckinError, setQrCheckinError] = useState<string | null>(null);
  const [qrCheckinSuccess, setQrCheckinSuccess] = useState<string | null>(null);

  const [staffList, setStaffList] = useState<StaffSession[]>([]);
  const [staffLoading, setStaffLoading] = useState(false);
  const [staffError, setStaffError] = useState<string | null>(null);
  const [staffForm, setStaffForm] = useState<StaffCreateForm>(EMPTY_STAFF_FORM);
  const [staffSuccess, setStaffSuccess] = useState<string | null>(null);
  const [staffSubmitting, setStaffSubmitting] = useState(false);

  useEffect(() => {
    if (status === "unauthenticated") {
      navigate(loginPath, onNavigate);
    }
  }, [loginPath, onNavigate, status]);

  useEffect(() => {
    if (status === "unauthenticated") {
      return;
    }

    void refreshSession();
  }, [refreshSession, status]);

  async function loadReservations(nextSelectedReservationId?: number | null) {
    setReservationsLoading(true);
    setReservationsError(null);

    try {
      const [listResponse, freshDetail] = await Promise.all([
        reservationsApi.list({
          status: filters.status || undefined,
          room_id: filters.roomId ? Number(filters.roomId) : undefined,
        }),
        nextSelectedReservationId
          ? reservationsApi.getById(nextSelectedReservationId)
          : Promise.resolve(null),
      ]);

      setReservations(listResponse.reservations);

      if (freshDetail) {
        setSelectedReservationId(freshDetail.id);
        setSelectedReservation(freshDetail);
      } else {
        const firstId = listResponse.reservations[0]?.id ?? null;
        setSelectedReservationId(firstId);
        if (firstId) {
          const first = await reservationsApi.getById(firstId);
          setSelectedReservation(first);
        } else {
          setSelectedReservation(null);
        }
      }
    } catch (error) {
      setReservationsError(
        friendlyError(error, "We could not load reservations right now."),
      );
      setSelectedReservation(null);
    } finally {
      setReservationsLoading(false);
    }
  }

  async function loadReservationDetail(reservationId: number) {
    setSelectedReservationId(reservationId);
    setReservationActionError(null);
    setReservationActionSuccess(null);

    try {
      const reservation = await reservationsApi.getById(reservationId);
      setSelectedReservation(reservation);
    } catch (error) {
      setReservationActionError(
        friendlyError(error, "We could not load that reservation."),
      );
    }
  }

  async function loadStaffList() {
    if (!isAdmin) {
      return;
    }

    setStaffLoading(true);
    setStaffError(null);

    try {
      const response = await adminApi.listStaff();
      setStaffList(response.staff);
    } catch (error) {
      setStaffError(friendlyError(error, "We could not load staff accounts."));
    } finally {
      setStaffLoading(false);
    }
  }

  useEffect(() => {
    if (status === "authenticated") {
      void loadReservations();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, filters.status, filters.roomId]);

  useEffect(() => {
    if (status === "authenticated" && isAdmin) {
      void loadStaffList();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, isAdmin]);

  async function handleLogout() {
    try {
      await logout();
    } finally {
      navigate(loginPath, onNavigate);
    }
  }

  function handleFilterChange(
    key: keyof ReservationFilters,
    event: ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) {
    setFilters((current) => ({
      ...current,
      [key]: event.target.value,
    }));
  }

  function handleCreateFormChange(
    key: keyof CreateReservationForm,
    event: ChangeEvent<HTMLInputElement>,
  ) {
    setCreateForm((current) => ({
      ...current,
      [key]: event.target.value,
    }));
  }

  function handleAvailabilityChange(
    key: keyof AvailabilityForm,
    event: ChangeEvent<HTMLInputElement>,
  ) {
    setAvailabilityForm((current) => ({
      ...current,
      [key]: event.target.value,
    }));
  }

  function handleStaffFormChange(
    key: keyof StaffCreateForm,
    event: ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) {
    setStaffForm((current) => ({
      ...current,
      [key]: event.target.value as StaffCreateForm[typeof key],
    }));
  }

  async function handleCreateReservation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateSubmitting(true);
    setCreateError(null);
    setCreateSuccess(null);

    try {
      const reservation = await reservationsApi.create({
        room_id: Number(createForm.room_id),
        check_in: createForm.check_in,
        check_out: createForm.check_out,
        guest_name: createForm.guest_name || undefined,
        guest_email: createForm.guest_email || undefined,
      });

      setCreateForm(EMPTY_CREATE_RESERVATION_FORM);
      setCreateSuccess(`Reservation #${reservation.id} created successfully.`);
      await loadReservations(reservation.id);
    } catch (error) {
      setCreateError(
        friendlyError(error, "We could not create that reservation."),
      );
    } finally {
      setCreateSubmitting(false);
    }
  }

  async function handleAvailabilityCheck(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAvailabilityLoading(true);
    setAvailabilityError(null);
    setAvailabilityResult(null);

    try {
      const response = await reservationsApi.availability({
        room_id: Number(availabilityForm.room_id),
        check_in: availabilityForm.check_in,
        check_out: availabilityForm.check_out,
      });

      setAvailabilityResult(response);
    } catch (error) {
      setAvailabilityError(
        friendlyError(error, "We could not check availability right now."),
      );
    } finally {
      setAvailabilityLoading(false);
    }
  }

  async function handleReservationAction(
    action: "checkin" | "checkout" | "cancel",
    reservationId: number,
  ) {
    setActionBusyKey(`${action}:${reservationId}`);
    setReservationActionError(null);
    setReservationActionSuccess(null);

    try {
      if (action === "checkin") {
        await reservationsApi.checkIn({ reservation_id: reservationId });
        setReservationActionSuccess(`Reservation #${reservationId} checked in.`);
        await loadReservations(reservationId);
      } else if (action === "checkout") {
        await reservationsApi.checkOut({ reservation_id: reservationId });
        setReservationActionSuccess(`Reservation #${reservationId} checked out.`);
        setSelectedReservation(null);
        setSelectedReservationId(null);
        await new Promise((resolve) => setTimeout(resolve, 100));
        await loadReservations(reservationId);
      } else {
        await reservationsApi.cancel(reservationId, { reason: cancelReason });
        setReservationActionSuccess(`Reservation #${reservationId} cancelled.`);
        setCancelReason("");
        setSelectedReservation(null);
        setSelectedReservationId(null);
        await new Promise((resolve) => setTimeout(resolve, 100));
        await loadReservations(reservationId);
      }
    } catch (error) {
      setReservationActionError(
        friendlyError(error, "We could not complete that reservation action."),
      );
    } finally {
      setActionBusyKey(null);
    }
  }

  async function handleQrCheckin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQrCheckinLoading(true);
    setQrCheckinError(null);
    setQrCheckinSuccess(null);

    try {
      // Use the staff endpoint to look up the reservation by token.
      // This keeps the staff JWT cookie intact — we never call the guest auth endpoint.
      const reservation = await reservationsApi.getByToken(qrToken.trim());

      if (reservation.status !== 'pending') {
        setQrCheckinError(
          reservation.status === 'active'
            ? 'Guest is already checked in.'
            : `Cannot check in: reservation is ${reservation.status}.`
        );
        return;
      }

      await reservationsApi.checkIn({ reservation_id: reservation.id });
      setQrCheckinSuccess(
        `Guest checked in. Room ${reservation.room_id}, Reservation #${reservation.id}.`
      );
      setQrToken('');
      await loadReservations(reservation.id);
    } catch (error) {
      setQrCheckinError(friendlyError(error, 'Token not found or check-in failed.'));
    } finally {
      setQrCheckinLoading(false);
    }
  }

  async function handleCreateStaff(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStaffSubmitting(true);
    setStaffError(null);
    setStaffSuccess(null);

    try {
      await adminApi.createStaff({
        email: staffForm.email,
        full_name: staffForm.full_name,
        password: staffForm.password,
        role: staffForm.role,
      });

      setStaffForm(EMPTY_STAFF_FORM);
      setStaffSuccess("Staff account created successfully.");
      await loadStaffList();
    } catch (error) {
      setStaffError(friendlyError(error, "We could not create that staff account."));
    } finally {
      setStaffSubmitting(false);
    }
  }

  async function handleStaffStatusToggle(staff: StaffSession) {
    setStaffError(null);
    setStaffSuccess(null);

    try {
      if (staff.is_active) {
        await adminApi.deactivateStaff(staff.id);
        setStaffSuccess(`Deactivated ${staff.full_name}.`);
      } else {
        await adminApi.reactivateStaff(staff.id);
        setStaffSuccess(`Reactivated ${staff.full_name}.`);
      }

      await loadStaffList();
    } catch (error) {
      setStaffError(
        friendlyError(error, "We could not update that staff account."),
      );
    }
  }

  const selectedStatusTone = selectedReservation
    ? statusTone(selectedReservation.status)
    : undefined;

  const reservationSummary = useMemo(() => {
    const active = reservations.filter((reservation) => reservation.status === "active").length;
    const pending = reservations.filter((reservation) => reservation.status === "pending").length;
    const checkedOut = reservations.filter(
      (reservation) => reservation.status === "checked_out",
    ).length;

    return { active, pending, checkedOut };
  }, [reservations]);

  if (status === "loading") {
    return <div>Loading your staff session...</div>;
  }

  if (!session) {
    return <div>Redirecting to login...</div>;
  }

  return (
    <main style={styles.page}>
      <section style={styles.shell}>
        <header style={styles.shellHeader}>
          <div>
            <p style={styles.eyebrow}>AirBnoB Staff Workspace</p>
            <h1 style={styles.title}>Welcome back, {session.full_name}</h1>
            <p style={styles.subtitle}>
              Signed in as <strong>{session.role}</strong>. Reservations, check-ins,
              availability, and staff management live here.
            </p>
          </div>
          <div style={styles.headerActions}>
            <button type="button" onClick={() => void loadReservations()} style={styles.secondaryButton}>
              Refresh data
            </button>
            <button type="button" onClick={() => void handleLogout()} style={styles.primaryButton}>
              Log out
            </button>
          </div>
        </header>

        <section style={styles.metricGrid}>
          <MetricCard label="Signed in" value={session.role} />
          <MetricCard label="Pending" value={String(reservationSummary.pending)} />
          <MetricCard label="Active stays" value={String(reservationSummary.active)} />
          <MetricCard label="Checked out" value={String(reservationSummary.checkedOut)} />
        </section>

        <section style={styles.workspaceGrid}>
          <div style={styles.column}>
            <Panel
              title="Reservations"
              subtitle="Filter by status or room, then select a reservation for detail and actions."
            >
              <div style={styles.filterRow}>
                <label style={styles.compactField}>
                  <span style={styles.fieldLabel}>Status</span>
                  <select
                    value={filters.status}
                    onChange={(event) => handleFilterChange("status", event)}
                    style={styles.select}
                  >
                    <option value="">All</option>
                    <option value="pending">Pending</option>
                    <option value="active">Active</option>
                    <option value="checked_out">Checked out</option>
                    <option value="cancelled">Cancelled</option>
                  </select>
                </label>

                <label style={styles.compactField}>
                  <span style={styles.fieldLabel}>Room</span>
                  <input
                    value={filters.roomId}
                    onChange={(event) => handleFilterChange("roomId", event)}
                    placeholder="101"
                    style={styles.input}
                  />
                </label>
              </div>

              {reservationsError ? <p style={styles.errorText}>{reservationsError}</p> : null}
              {reservationsLoading ? <p style={styles.mutedText}>Loading reservations...</p> : null}

              <div style={styles.list}>
                {reservations.map((reservation) => (
                  <button
                    key={reservation.id}
                    type="button"
                    onClick={() => void loadReservationDetail(reservation.id)}
                    style={{
                      ...styles.listItem,
                      ...(selectedReservationId === reservation.id
                        ? styles.listItemSelected
                        : null),
                    }}
                  >
                    <div style={styles.listItemHeader}>
                      <strong>Reservation #{reservation.id}</strong>
                      <span style={{ ...styles.badge, ...statusTone(reservation.status) }}>
                        {reservation.status}
                      </span>
                    </div>
                    <span style={styles.listItemMeta}>
                      Room {reservation.room_id} • {formatDate(reservation.check_in)} -{" "}
                      {formatDate(reservation.check_out)}
                    </span>
                  </button>
                ))}

                {!reservationsLoading && reservations.length === 0 ? (
                  <p style={styles.mutedText}>No reservations match the current filters.</p>
                ) : null}
              </div>
            </Panel>

            <Panel
              title="Create reservation"
              subtitle="Front desk and admin can create a reservation directly from this workspace."
            >
              <form onSubmit={handleCreateReservation} style={styles.form}>
                <FormRow>
                  <Field label="Room">
                    <input
                      value={createForm.room_id}
                      onChange={(event) => handleCreateFormChange("room_id", event)}
                      placeholder="301"
                      style={styles.input}
                    />
                  </Field>
                  <Field label="Guest name">
                    <input
                      value={createForm.guest_name}
                      onChange={(event) => handleCreateFormChange("guest_name", event)}
                      placeholder="Taylor Guest"
                      style={styles.input}
                    />
                  </Field>
                </FormRow>

                <FormRow>
                  <Field label="Check-in">
                    <input
                      type="date"
                      value={createForm.check_in}
                      onChange={(event) => handleCreateFormChange("check_in", event)}
                      style={styles.input}
                    />
                  </Field>
                  <Field label="Check-out">
                    <input
                      type="date"
                      value={createForm.check_out}
                      onChange={(event) => handleCreateFormChange("check_out", event)}
                      style={styles.input}
                    />
                  </Field>
                </FormRow>

                <Field label="Guest email">
                  <input
                    type="email"
                    value={createForm.guest_email}
                    onChange={(event) => handleCreateFormChange("guest_email", event)}
                    placeholder="guest@example.com"
                    style={styles.input}
                  />
                </Field>

                {createError ? <p style={styles.errorText}>{createError}</p> : null}
                {createSuccess ? <p style={styles.successText}>{createSuccess}</p> : null}

                <button type="submit" disabled={createSubmitting} style={styles.primaryButton}>
                  {createSubmitting ? "Creating..." : "Create reservation"}
                </button>
              </form>
            </Panel>

            <Panel
              title="Availability"
              subtitle="Check a room before booking so conflicts are obvious before staff act."
            >
              <form onSubmit={handleAvailabilityCheck} style={styles.form}>
                <FormRow>
                  <Field label="Room">
                    <input
                      value={availabilityForm.room_id}
                      onChange={(event) => handleAvailabilityChange("room_id", event)}
                      placeholder="505"
                      style={styles.input}
                    />
                  </Field>
                  <Field label="Check-in">
                    <input
                      type="date"
                      value={availabilityForm.check_in}
                      onChange={(event) => handleAvailabilityChange("check_in", event)}
                      style={styles.input}
                    />
                  </Field>
                  <Field label="Check-out">
                    <input
                      type="date"
                      value={availabilityForm.check_out}
                      onChange={(event) => handleAvailabilityChange("check_out", event)}
                      style={styles.input}
                    />
                  </Field>
                </FormRow>

                <button
                  type="submit"
                  disabled={availabilityLoading}
                  style={styles.secondaryButton}
                >
                  {availabilityLoading ? "Checking..." : "Check availability"}
                </button>
              </form>

              {availabilityError ? <p style={styles.errorText}>{availabilityError}</p> : null}

              {availabilityResult ? (
                <div style={styles.resultBlock}>
                  <p style={availabilityResult.available ? styles.successText : styles.errorText}>
                    {availabilityResult.available
                      ? `Room ${availabilityResult.room_id} is available.`
                      : `Room ${availabilityResult.room_id} has conflicts in that window.`}
                  </p>
                  {!availabilityResult.available ? (
                    <ul style={styles.conflictList}>
                      {availabilityResult.conflicts.map((conflict) => (
                        <li key={conflict.id}>
                          Reservation #{conflict.id} • {formatDate(conflict.check_in)} -{" "}
                          {formatDate(conflict.check_out)} • {conflict.status}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}
            </Panel>
          </div>

          <div style={styles.column}>
            <Panel
              title="Guest QR Check-in"
              subtitle="Enter the token from a guest's QR code to look up and check them in instantly."
            >
              <form onSubmit={(e) => void handleQrCheckin(e)} style={styles.form}>
                <Field label="QR / access token">
                  <input
                    autoComplete="off"
                    value={qrToken}
                    onChange={(event) => setQrToken(event.target.value)}
                    placeholder="123e4567-e89b-42d3-a456-426614174000"
                    style={styles.input}
                  />
                </Field>
                <button
                  type="submit"
                  disabled={qrCheckinLoading || qrToken.trim().length === 0}
                  style={styles.primaryButton}
                >
                  {qrCheckinLoading ? "Checking in..." : "Check in guest"}
                </button>
              </form>
              {qrCheckinError ? <p style={{ ...styles.errorText, marginTop: "12px" }}>{qrCheckinError}</p> : null}
              {qrCheckinSuccess ? <p style={{ ...styles.successText, marginTop: "12px" }}>{qrCheckinSuccess}</p> : null}
            </Panel>

            <Panel
              title="Reservation detail"
              subtitle="Inspect the selected reservation and run the allowed lifecycle actions."
            >
              {!selectedReservation ? (
                <p style={styles.mutedText}>
                  Choose a reservation from the list to inspect and act on it.
                </p>
              ) : (
                <div style={styles.detailStack}>
                  <div style={styles.detailHeader}>
                    <div>
                      <h2 style={styles.detailTitle}>
                        Reservation #{selectedReservation.id}
                      </h2>
                      <p style={styles.detailSubtitle}>
                        Room {selectedReservation.room_id} •{" "}
                        {selectedReservation.guest_name || "Guest name not provided"}
                      </p>
                    </div>
                    <span style={{ ...styles.badge, ...selectedStatusTone }}>
                      {selectedReservation.status}
                    </span>
                  </div>

                  <dl style={styles.detailGrid}>
                    <DetailItem label="Check-in" value={formatDate(selectedReservation.check_in)} />
                    <DetailItem label="Check-out" value={formatDate(selectedReservation.check_out)} />
                    <DetailItem label="Guest email" value={selectedReservation.guest_email || "Not provided"} />
                    <DetailItem label="Nights" value={String(selectedReservation.nights)} />
                  </dl>

                  {reservationActionError ? (
                    <p style={styles.errorText}>{reservationActionError}</p>
                  ) : null}
                  {reservationActionSuccess ? (
                    <p style={styles.successText}>{reservationActionSuccess}</p>
                  ) : null}

                  <div style={styles.actionRow}>
                    <button
                      type="button"
                      disabled={
                        selectedReservation.status !== "pending" ||
                        actionBusyKey === `checkin:${selectedReservation.id}`
                      }
                      onClick={() =>
                        void handleReservationAction("checkin", selectedReservation.id)
                      }
                      style={styles.primaryButton}
                    >
                      {actionBusyKey === `checkin:${selectedReservation.id}`
                        ? "Checking in..."
                        : "Check in"}
                    </button>

                    <button
                      type="button"
                      disabled={
                        selectedReservation.status !== "active" ||
                        actionBusyKey === `checkout:${selectedReservation.id}`
                      }
                      onClick={() =>
                        void handleReservationAction("checkout", selectedReservation.id)
                      }
                      style={styles.secondaryButton}
                    >
                      {actionBusyKey === `checkout:${selectedReservation.id}`
                        ? "Checking out..."
                        : "Check out"}
                    </button>
                  </div>

                  <div style={styles.cancelBox}>
                    <Field label="Cancellation reason">
                      <input
                        value={cancelReason}
                        onChange={(event) => setCancelReason(event.target.value)}
                        placeholder="Reason for cancellation"
                        style={styles.input}
                      />
                    </Field>

                    <button
                      type="button"
                      disabled={
                        selectedReservation.status !== "pending" ||
                        cancelReason.trim().length < 5 ||
                        actionBusyKey === `cancel:${selectedReservation.id}`
                      }
                      onClick={() =>
                        void handleReservationAction("cancel", selectedReservation.id)
                      }
                      style={styles.dangerButton}
                    >
                      {actionBusyKey === `cancel:${selectedReservation.id}`
                        ? "Cancelling..."
                        : "Cancel reservation"}
                    </button>
                  </div>
                </div>
              )}
            </Panel>

            {isAdmin ? (
              <Panel
                title="Staff management"
                subtitle="Admins can create staff accounts and reactivate or deactivate them."
              >
                <form onSubmit={handleCreateStaff} style={styles.form}>
                  <FormRow>
                    <Field label="Full name">
                      <input
                        value={staffForm.full_name}
                        onChange={(event) => handleStaffFormChange("full_name", event)}
                        placeholder="Kritika Upadhyay"
                        style={styles.input}
                      />
                    </Field>
                    <Field label="Role">
                      <select
                        value={staffForm.role}
                        onChange={(event) => handleStaffFormChange("role", event)}
                        style={styles.select}
                      >
                        <option value="front_desk">front_desk</option>
                        <option value="admin">admin</option>
                      </select>
                    </Field>
                  </FormRow>

                  <FormRow>
                    <Field label="Email">
                      <input
                        type="email"
                        value={staffForm.email}
                        onChange={(event) => handleStaffFormChange("email", event)}
                        placeholder="staff@airbnob.local"
                        style={styles.input}
                      />
                    </Field>
                    <Field label="Password">
                      <input
                        type="password"
                        value={staffForm.password}
                        onChange={(event) => handleStaffFormChange("password", event)}
                        placeholder="Create a strong password"
                        style={styles.input}
                      />
                    </Field>
                  </FormRow>

                  <button type="submit" disabled={staffSubmitting} style={styles.primaryButton}>
                    {staffSubmitting ? "Creating..." : "Create staff account"}
                  </button>
                </form>

                {staffError ? <p style={styles.errorText}>{staffError}</p> : null}
                {staffSuccess ? <p style={styles.successText}>{staffSuccess}</p> : null}

                <div style={styles.staffList}>
                  {staffLoading ? <p style={styles.mutedText}>Loading staff accounts...</p> : null}
                  {staffList.map((staff) => (
                    <div key={staff.id} style={styles.staffItem}>
                      <div>
                        <strong>{staff.full_name}</strong>
                        <p style={styles.staffMeta}>
                          {staff.email} • {staff.role} •{" "}
                          {staff.is_active ? "active" : "inactive"}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleStaffStatusToggle(staff)}
                        style={styles.secondaryButton}
                      >
                        {staff.is_active ? "Deactivate" : "Reactivate"}
                      </button>
                    </div>
                  ))}
                </div>
              </Panel>
            ) : (
              <Panel
                title="Staff access"
                subtitle="Front desk users can manage reservations and guest stays, but not staff accounts."
              >
                <p style={styles.mutedText}>
                  Your role is limited to reservation, check-in, checkout, cancellation,
                  and availability workflows.
                </p>
              </Panel>
            )}
          </div>
        </section>
      </section>
    </main>
  );
}

function Panel({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <section style={styles.panel}>
      <header style={styles.panelHeader}>
        <h2 style={styles.panelTitle}>{title}</h2>
        <p style={styles.panelSubtitle}>{subtitle}</p>
      </header>
      {children}
    </section>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label style={styles.field}>
      <span style={styles.fieldLabel}>{label}</span>
      {children}
    </label>
  );
}

function FormRow({ children }: { children: ReactNode }) {
  return <div style={styles.formRow}>{children}</div>;
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={styles.metricCard}>
      <span style={styles.metricLabel}>{label}</span>
      <strong style={styles.metricValue}>{value}</strong>
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div style={styles.detailItem}>
      <dt style={styles.term}>{label}</dt>
      <dd style={styles.value}>{value}</dd>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  page: {
    minHeight: "100vh",
    background: "#f4fff4",
    padding: "32px",
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    color: "#0f172a",
  },
  shell: {
    maxWidth: "1400px",
    margin: "0 auto",
    display: "grid",
    gap: "24px",
  },
  shellHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: "16px",
    background: "#ffffff",
    border: "1px solid rgba(47, 111, 18, 0.06)",
    borderRadius: "8px",
    padding: "28px 32px",
    boxShadow: "0 10px 28px rgba(15, 23, 42, 0.05)",
  },
  headerActions: {
    display: "flex",
    gap: "12px",
    alignItems: "center",
  },
  eyebrow: {
    margin: "0 0 8px",
    fontSize: "12px",
    textTransform: "uppercase",
    fontWeight: 700,
    color: "#475569",
  },
  title: {
    margin: 0,
    fontSize: "32px",
    lineHeight: 1.1,
  },
  subtitle: {
    margin: "8px 0 0",
    color: "#475569",
    maxWidth: "760px",
  },
  metricGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "16px",
  },
  metricCard: {
    background: "#ffffff",
    border: "1px solid rgba(47, 111, 18, 0.06)",
    borderRadius: "8px",
    padding: "18px 20px",
    display: "grid",
    gap: "8px",
  },
  metricLabel: {
    fontSize: "12px",
    textTransform: "uppercase",
    fontWeight: 700,
    color: "#64748b",
  },
  metricValue: {
    fontSize: "24px",
    lineHeight: 1.1,
  },
  workspaceGrid: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1.2fr) minmax(0, 1fr)",
    gap: "24px",
  },
  column: {
    display: "grid",
    gap: "24px",
    alignContent: "start",
  },
  panel: {
    background: "#ffffff",
    border: "1px solid #e2e8f0",
    borderRadius: "8px",
    padding: "24px",
    boxShadow: "0 10px 28px rgba(15, 23, 42, 0.05)",
  },
  panelHeader: {
    display: "grid",
    gap: "6px",
    marginBottom: "18px",
  },
  panelTitle: {
    margin: 0,
    fontSize: "20px",
    lineHeight: 1.2,
  },
  panelSubtitle: {
    margin: 0,
    color: "#64748b",
    fontSize: "14px",
    lineHeight: 1.5,
  },
  filterRow: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 180px) minmax(0, 180px)",
    gap: "12px",
    marginBottom: "16px",
  },
  compactField: {
    display: "grid",
    gap: "8px",
  },
  list: {
    display: "grid",
    gap: "12px",
  },
  listItem: {
    padding: "14px 16px",
    borderRadius: "8px",
    border: "1px solid #e2e8f0",
    background: "#f8fafc",
    textAlign: "left",
    cursor: "pointer",
    display: "grid",
    gap: "8px",
  },
  listItemSelected: {
    background: "#eff6ff",
    borderColor: "#93c5fd",
  },
  listItemHeader: {
    display: "flex",
    justifyContent: "space-between",
    gap: "12px",
    alignItems: "center",
  },
  listItemMeta: {
    color: "#64748b",
    fontSize: "14px",
  },
  badge: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    minHeight: "28px",
    padding: "0 10px",
    borderRadius: "999px",
    fontSize: "12px",
    fontWeight: 700,
    textTransform: "capitalize",
  },
  form: {
    display: "grid",
    gap: "16px",
  },
  formRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "12px",
  },
  field: {
    display: "grid",
    gap: "8px",
  },
  fieldLabel: {
    fontSize: "13px",
    fontWeight: 700,
    color: "#334155",
  },
  input: {
    width: "100%",
    minHeight: "42px",
    border: "1px solid #cbd5e1",
    borderRadius: "8px",
    padding: "0 12px",
    boxSizing: "border-box",
    fontSize: "14px",
    background: "#ffffff",
  },
  select: {
    width: "100%",
    minHeight: "42px",
    border: "1px solid #cbd5e1",
    borderRadius: "8px",
    padding: "0 12px",
    boxSizing: "border-box",
    fontSize: "14px",
    background: "#ffffff",
  },
  primaryButton: {
    minHeight: "42px",
    borderRadius: "8px",
    border: "none",
    background: "#0f172a",
    color: "#ffffff",
    fontWeight: 700,
    padding: "0 16px",
    cursor: "pointer",
  },
  secondaryButton: {
    minHeight: "42px",
    borderRadius: "8px",
    border: "1px solid #cbd5e1",
    background: "#ffffff",
    color: "#0f172a",
    fontWeight: 700,
    padding: "0 16px",
    cursor: "pointer",
  },
  dangerButton: {
    minHeight: "42px",
    borderRadius: "8px",
    border: "none",
    background: "#b91c1c",
    color: "#ffffff",
    fontWeight: 700,
    padding: "0 16px",
    cursor: "pointer",
  },
  mutedText: {
    margin: 0,
    color: "#64748b",
  },
  errorText: {
    margin: 0,
    color: "#b91c1c",
    fontWeight: 600,
  },
  successText: {
    margin: 0,
    color: "#166534",
    fontWeight: 600,
  },
  resultBlock: {
    marginTop: "14px",
    display: "grid",
    gap: "8px",
  },
  conflictList: {
    margin: 0,
    paddingLeft: "18px",
    color: "#475569",
  },
  detailStack: {
    display: "grid",
    gap: "18px",
  },
  detailHeader: {
    display: "flex",
    justifyContent: "space-between",
    gap: "16px",
    alignItems: "flex-start",
  },
  detailTitle: {
    margin: 0,
    fontSize: "24px",
    lineHeight: 1.1,
  },
  detailSubtitle: {
    margin: "8px 0 0",
    color: "#64748b",
  },
  detailGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "12px",
    margin: 0,
  },
  detailItem: {
    margin: 0,
    padding: "14px 16px",
    border: "1px solid #e2e8f0",
    borderRadius: "8px",
    background: "#f8fafc",
  },
  term: {
    fontSize: "12px",
    textTransform: "uppercase",
    fontWeight: 700,
    color: "#64748b",
    marginBottom: "8px",
  },
  value: {
    margin: 0,
    fontSize: "15px",
    fontWeight: 600,
  },
  actionRow: {
    display: "flex",
    gap: "12px",
    flexWrap: "wrap",
  },
  cancelBox: {
    display: "grid",
    gap: "12px",
    paddingTop: "8px",
    borderTop: "1px solid #e2e8f0",
  },
  staffList: {
    display: "grid",
    gap: "12px",
    marginTop: "18px",
  },
  staffItem: {
    display: "flex",
    justifyContent: "space-between",
    gap: "16px",
    alignItems: "center",
    border: "1px solid #e2e8f0",
    borderRadius: "8px",
    padding: "14px 16px",
    background: "#f8fafc",
  },
  staffMeta: {
    margin: "6px 0 0",
    color: "#64748b",
    fontSize: "14px",
  },
};
