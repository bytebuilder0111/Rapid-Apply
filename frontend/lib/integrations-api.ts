import { api } from "@/lib/api";

export type OpenAiSettings = {
  has_key: boolean;
  masked_key: string | null;
  model: string;
};

export type GoogleConnection = {
  connected: boolean;
  email: string | null;
  status: "CONNECTED" | "NEEDS_RECONNECT" | null;
};

export const integrationsApi = {
  getOpenAi: () => api.get<OpenAiSettings>("/integrations/openai"),
  saveOpenAi: (input: { api_key: string; model?: string }) =>
    api.put<OpenAiSettings>("/integrations/openai", input),
  deleteOpenAi: () => api.delete<void>("/integrations/openai"),
  testOpenAi: () => api.post<void>("/integrations/openai/test"),

  getGoogle: () => api.get<GoogleConnection>("/integrations/google"),
  getGoogleAuthorizeUrl: () =>
    api.get<{ authorize_url: string }>("/integrations/google/authorize"),
  disconnectGoogle: () => api.delete<void>("/integrations/google"),
};
