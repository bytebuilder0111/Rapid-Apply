import { api } from "@/lib/api";
import type { TechStack } from "@/lib/types";

// Any authenticated user (building a profile) sees only active stacks.
export const techStacksApi = {
  listActive: () => api.get<TechStack[]>("/tech-stacks"),
};

export type TechStackUpdateInput = { name?: string; is_active?: boolean };

// ADMIN only — full management.
export const adminTechStacksApi = {
  listAll: () => api.get<TechStack[]>("/admin/tech-stacks"),
  create: (name: string) => api.post<TechStack>("/admin/tech-stacks", { name }),
  update: (id: string, input: TechStackUpdateInput) =>
    api.patch<TechStack>(`/admin/tech-stacks/${id}`, input),
  remove: (id: string) => api.delete<void>(`/admin/tech-stacks/${id}`),
};
