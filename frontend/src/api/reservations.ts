import { apiRequest } from "./client";
import type {
  AvailabilityQuery,
  AvailabilityResponse,
  CancelReservationRequest,
  CancelReservationResponse,
  CheckInRequest,
  CheckInResponse,
  CheckOutRequest,
  CheckOutResponse,
  CreateReservationRequest,
  GuestBookingRequest,
  GuestBookingResponse,
  Reservation,
  ReservationListResponse,
  ReservationStatus,
  UpdateReservationRequest,
} from "./types";

type ReservationListQuery = {
  status?: ReservationStatus;
  room_id?: number;
};

export const reservationsApi = {
  list(query: ReservationListQuery = {}) {
    return apiRequest<ReservationListResponse>("/staff/reservations", {
      query,
    });
  },

  getById(reservationId: number) {
    return apiRequest<Reservation>(`/staff/reservations/${reservationId}`);
  },

  create(payload: CreateReservationRequest) {
    return apiRequest<Reservation>("/staff/reservations", {
      method: "POST",
      body: payload,
    });
  },

  guestBook(payload: GuestBookingRequest) {
    return apiRequest<GuestBookingResponse>("/guest/book", {
      method: "POST",
      body: payload,
    });
  },

  update(reservationId: number, payload: UpdateReservationRequest) {
    return apiRequest<Reservation>(`/staff/reservations/${reservationId}`, {
      method: "PATCH",
      body: payload,
    });
  },

  cancel(reservationId: number, payload: CancelReservationRequest) {
    return apiRequest<CancelReservationResponse>(
      `/staff/reservations/${reservationId}/cancel`,
      {
        method: "POST",
        body: payload,
      },
    );
  },

  checkIn(payload: CheckInRequest) {
    return apiRequest<CheckInResponse>("/staff/checkin", {
      method: "POST",
      body: payload,
    });
  },

  checkOut(payload: CheckOutRequest) {
    return apiRequest<CheckOutResponse>("/staff/checkout", {
      method: "POST",
      body: payload,
    });
  },

  getByToken(token: string) {
    return apiRequest<Reservation>(`/staff/reservations/by-token/${token}`);
  },

  availability(query: AvailabilityQuery) {
    return apiRequest<AvailabilityResponse>("/staff/availability", {
      query,
    });
  },
};
