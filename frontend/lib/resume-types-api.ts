import { api } from "@/lib/api";
import type { ResumeType } from "@/lib/types";

export const resumeTypesApi = {
  /** A profile's resume types, or all of the client's when profileId is omitted. Admins pass clientId. */
  list: (params: { profileId?: string; clientId?: string } = {}) => {
    const query = new URLSearchParams();
    if (params.profileId) query.set("profile_id", params.profileId);
    if (params.clientId) query.set("client_id", params.clientId);
    const qs = query.toString();
    return api.get<ResumeType[]>(`/resume-types${qs ? `?${qs}` : ""}`);
  },
  create: (input: { profile_id: string; name: string }) =>
    api.post<ResumeType>("/resume-types", input),
  update: (id: string, input: { name?: string; is_active?: boolean }) =>
    api.patch<ResumeType>(`/resume-types/${id}`, input),
  remove: (id: string) => api.delete<void>(`/resume-types/${id}`),
  uploadResume: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.post<ResumeType>(`/resume-types/${id}/resume`, form);
  },
};
