// Local device config: bearer token + API base URL (single-user, localStorage-backed).

const TOKEN_KEY = "subjects_token";
const BASE_KEY = "subjects_api_base";

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || "";
}
export function setToken(t: string): void {
  localStorage.setItem(TOKEN_KEY, t);
}
export function getApiBase(): string {
  // Empty => same origin (dev proxy / docker web reverse-proxy).
  return localStorage.getItem(BASE_KEY) || "";
}
export function setApiBase(b: string): void {
  localStorage.setItem(BASE_KEY, b.replace(/\/$/, ""));
}
