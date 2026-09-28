import { api } from "@/lib/api";
import type { Profile, ProfileInput } from "@/lib/types";

export type ProfileUpdateInput = Partial<ProfileInput> & { is_active?: boolean };

export const profilesApi = {
  list: (clientId?: string) =>
    api.get<Profile[]>(`/profiles${clientId ? `?client_id=${clientId}` : ""}`),
  create: (input: ProfileInput) => api.post<Profile>("/profiles", input),
  update: (id: string, input: ProfileUpdateInput) => api.patch<Profile>(`/profiles/${id}`, input),
  remove: (id: string) => api.delete<void>(`/profiles/${id}`),
};
