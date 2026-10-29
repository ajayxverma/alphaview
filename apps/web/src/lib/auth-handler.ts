import { NextRequest, NextResponse } from "next/server";
import { API_URL, SESSION_COOKIE, sessionCookieOptions } from "@/lib/session";

/** Exchanges credentials with the backend and stores the JWT in an httpOnly cookie. */
export async function authenticate(req: NextRequest, endpoint: "login" | "register") {
  const body = await req.text();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const forwardedFor = req.headers.get("x-forwarded-for");
  if (forwardedFor) headers["X-Forwarded-For"] = forwardedFor;
  const res = await fetch(`${API_URL}/auth/${endpoint}`, {
    method: "POST",
    headers,
    body,
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    return NextResponse.json(data, { status: res.status });
  }
  const response = NextResponse.json({ ok: true });
  response.cookies.set(SESSION_COOKIE, data.access_token, sessionCookieOptions);
  return response;
}
