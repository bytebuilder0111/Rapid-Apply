import { api } from "@/lib/api";
import type { BidderUser, ClientUser, DashboardCounts } from "@/lib/types";

export type ClientCreateInput = { username: string; name: string; password: string };
export type ClientUpdateInput = { username?: string; name?: string };
/** The client is taken from the assigned profile; the name defaults to the username. */
export type BidderCreateInput = {
  username: string;
  password: string;
  assigned_profile_id: string;
  name?: string;
};
export type BidderUpdateInput = { username?: string; name?: string; assigned_profile_id?: string };

export const adminApi = {
  dashboard: () => api.get<DashboardCounts>("/admin/dashboard"),

  listClients: (search?: string) =>
    api.get<ClientUser[]>(`/admin/clients${search ? `?search=${encodeURIComponent(search)}` : ""}`),
  createClient: (input: ClientCreateInput) => api.post<ClientUser>("/admin/clients", input),
  updateClient: (id: string, input: ClientUpdateInput) =>
    api.patch<ClientUser>(`/admin/clients/${id}`, input),
  deactivateClient: (id: string) => api.post<ClientUser>(`/admin/clients/${id}/deactivate`),
  reactivateClient: (id: string) => api.post<ClientUser>(`/admin/clients/${id}/reactivate`),
  resetClientPassword: (id: string, new_password: string) =>
    api.post<void>(`/admin/clients/${id}/reset-password`, { new_password }),
  deleteClient: (id: string) => api.delete<ClientUser>(`/admin/clients/${id}`),

  listBidders: (params?: { client_id?: string; search?: string }) => {
    const query = new URLSearchParams();
    if (params?.client_id) query.set("client_id", params.client_id);
    if (params?.search) query.set("search", params.search);
    const qs = query.toString();
    return api.get<BidderUser[]>(`/admin/bidders${qs ? `?${qs}` : ""}`);
  },
  createBidder: (input: BidderCreateInput) => api.post<BidderUser>("/admin/bidders", input),
  updateBidder: (id: string, input: BidderUpdateInput) =>
    api.patch<BidderUser>(`/admin/bidders/${id}`, input),
  deactivateBidder: (id: string) => api.post<BidderUser>(`/admin/bidders/${id}/deactivate`),
  reactivateBidder: (id: string) => api.post<BidderUser>(`/admin/bidders/${id}/reactivate`),
  resetBidderPassword: (id: string, new_password: string) =>
    api.post<void>(`/admin/bidders/${id}/reset-password`, { new_password }),
};
