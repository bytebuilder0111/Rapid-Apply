import { api } from "@/lib/api";

export type OpenAiSettings = {
  has_key: boolean;
  masked_key: string | null;
  model: string;
};

export const integrationsApi = {
  getOpenAi: () => api.get<OpenAiSettings>("/integrations/openai"),
  saveOpenAi: (input: { api_key: string; model?: string }) =>
    api.put<OpenAiSettings>("/integrations/openai", input),
  deleteOpenAi: () => api.delete<void>("/integrations/openai"),
  testOpenAi: () => api.post<void>("/integrations/openai/test"),
};
