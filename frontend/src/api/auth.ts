import { apiRequest } from "./client";
import type {
  ChangePasswordRequest,
  GuestSession,
  GuestVerifyRequest,
  Reservation,
  StaffLoginRequest,
  StaffLoginResponse,
  StaffSession,
} from "./types";

export const authApi = {
  login(payload: StaffLoginRequest) {
    return apiRequest<StaffLoginResponse>("/auth/staff/login", {
      method: "POST",
      body: payload,
    });
  },

  logout() {
    return apiRequest<{ message: string }>("/auth/staff/logout", {
      method: "POST",
    });
  },

  me() {
    return apiRequest<StaffSession>("/auth/staff/me");
  },

  changePassword(payload: ChangePasswordRequest) {
    return apiRequest<{ message: string }>("/auth/staff/change-password", {
      method: "POST",
      body: payload,
    });
  },
};

export const guestAuthApi = {
  verify(payload: GuestVerifyRequest) {
    return apiRequest<GuestSession>("/auth/guest/verify", {
      method: "POST",
      body: payload,
    });
  },

  me() {
    return apiRequest<GuestSession>("/guest/me");
  },

  reservation() {
    return apiRequest<Reservation>("/guest/reservation");
  },

  logout() {
    return apiRequest<{ message: string }>("/guest/logout", {
      method: "POST",
    });
  },
};
