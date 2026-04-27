export type StaffRole = "admin" | "front_desk";

export type ApiErrorCode =
  | "unauthorized"
  | "forbidden"
  | "validation"
  | "rate_limited"
  | "not_found"
  | "conflict"
  | "bad_request"
  | "server_error"
  | "unknown";

export type FieldErrors = Record<string, string[]>;

export type ApiError = {
  name: "ApiError";
  status: number;
  code: ApiErrorCode;
  message: string;
  fieldErrors?: FieldErrors;
  details?: unknown;
};

export type ErrorPayload = {
  detail: string;
};

export type StaffLoginRequest = {
  email: string;
  password: string;
};

export type StaffLoginResponse = {
  message: string;
  role: StaffRole;
  full_name: string;
};

export type StaffSession = {
  id: number;
  email: string;
  full_name: string;
  role: StaffRole;
  is_active: boolean;
};

export type ChangePasswordRequest = {
  current_password: string;
  new_password: string;
};

export type GuestVerifyRequest = {
  token: string;
};

export type GuestSession = {
  room_id: number;
  check_in: string;
  check_out: string;
  message: string;
};

export type ReservationStatus =
  | "pending"
  | "active"
  | "checked_out"
  | "cancelled";

export type Reservation = {
  id: number;
  room_id: number;
  status: ReservationStatus;
  check_in: string;
  check_out: string;
  nights: number;
  created_at: string;
  updated_at: string;
  guest_id: number | null;
  guest_name: string | null;
  guest_email: string | null;
};

export type ReservationListResponse = {
  reservations: Reservation[];
  total: number;
  status_filter: ReservationStatus | null;
};

export type CreateReservationRequest = {
  room_id: number;
  check_in: string;
  check_out: string;
  guest_name?: string | null;
  guest_email?: string | null;
};

export type GuestBookingRequest = CreateReservationRequest;

export type GuestBookingResponse = {
  message: string;
  guest_token: string;
  reservation: Reservation;
};

export type UpdateReservationRequest = Partial<
  Pick<CreateReservationRequest, "check_in" | "check_out" | "guest_name" | "guest_email">
>;

export type CancelReservationRequest = {
  reason: string;
};

export type CancelReservationResponse = {
  message: string;
  reason: string;
  reservation: Reservation;
};

export type CheckInRequest = {
  reservation_id: number;
};

export type CheckInResponse = {
  message: string;
  reservation_id: number;
  room_id: number;
  check_out: string;
};

export type CheckOutRequest = {
  reservation_id: number;
};

export type CheckOutResponse = {
  message: string;
  reservation_id: number;
  room_id: number;
  checked_out_at: string;
};

export type AvailabilityResponse = {
  room_id: number;
  available: boolean;
  conflicts: Reservation[];
};

export type AvailabilityQuery = {
  room_id: number;
  check_in: string;
  check_out: string;
};

export type CreateStaffRequest = {
  email: string;
  full_name: string;
  password: string;
  role: StaffRole;
};

export type StaffListResponse = {
  staff: StaffSession[];
  total: number;
};

export type StaffStatusResponse = StaffSession;
