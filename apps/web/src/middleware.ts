import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE } from "@/lib/session";

export function middleware(req: NextRequest) {
  if (!req.cookies.has(SESSION_COOKIE)) {
    const url = new URL("/login", req.url);
    url.searchParams.set("next", req.nextUrl.pathname);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/runs/:path*", "/opportunities/:path*", "/integrations/:path*"],
};
