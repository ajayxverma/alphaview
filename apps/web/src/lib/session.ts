export const SESSION_COOKIE = "av_token";
export const API_URL = process.env.API_URL ?? "http://localhost:8000";

export const sessionCookieOptions = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/",
  maxAge: 60 * 60 * 12,
};
