import { NextRequest } from "next/server";
import { authenticate } from "@/lib/auth-handler";

export async function POST(req: NextRequest) {
  return authenticate(req, "login");
}
