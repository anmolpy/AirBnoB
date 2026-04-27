import { apiRequest } from "./client";
import type {
  CreateStaffRequest,
  StaffListResponse,
  StaffStatusResponse,
} from "./types";

export const adminApi = {
  listStaff() {
    return apiRequest<StaffListResponse>("/admin/staff");
  },

  createStaff(payload: CreateStaffRequest) {
    return apiRequest<StaffStatusResponse>("/admin/staff", {
      method: "POST",
      body: payload,
    });
  },

  deactivateStaff(staffId: number) {
    return apiRequest<StaffStatusResponse>(`/admin/staff/${staffId}/deactivate`, {
      method: "PATCH",
    });
  },

  reactivateStaff(staffId: number) {
    return apiRequest<StaffStatusResponse>(`/admin/staff/${staffId}/reactivate`, {
      method: "PATCH",
    });
  },
};
