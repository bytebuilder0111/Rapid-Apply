export type Role = "ADMIN" | "CLIENT" | "BIDDER";

export type UserOut = {
  id: string;
  email: string;
  name: string;
  role: Role;
  client_id: string | null;
  assigned_profile_id: string | null;
  is_active: boolean;
  created_at: string;
};

// Access token lives in memory only (never localStorage) so a page reload always
// re-derives it from the httpOnly refresh cookie via POST /auth/refresh.
let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function roleHomePath(role: Role): string {
  switch (role) {
    case "ADMIN":
      return "/admin";
    case "CLIENT":
      return "/client";
    case "BIDDER":
      return "/bidder";
  }
}
