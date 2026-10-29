import { NextRequest, NextResponse } from "next/server";
import { API_URL, SESSION_COOKIE } from "@/lib/session";

type Ctx = { params: Promise<{ path: string[] }> };

async function forward(req: NextRequest, { params }: Ctx) {
  const token = req.cookies.get(SESSION_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }
  const { path } = await params;
  const target = `${API_URL}/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  const hasBody = req.method !== "GET" && req.method !== "DELETE";

  const res = await fetch(target, {
    method: req.method,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: hasBody ? await req.text() : undefined,
    cache: "no-store",
  });

  const response = new NextResponse(res.status === 204 ? null : await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
  if (res.status === 401) response.cookies.delete(SESSION_COOKIE);
  return response;
}

export { forward as GET, forward as POST, forward as DELETE };
