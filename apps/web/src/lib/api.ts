export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function detailMessage(data: unknown): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  }
  return "Request failed";
}

/** Browser-side call to the FastAPI backend through the authenticated Next.js proxy. */
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/proxy/${path.replace(/^\//, "")}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (res.status === 401) {
    window.location.href = "/login";
    throw new ApiError(401, "Session expired");
  }
  if (!res.ok) {
    throw new ApiError(res.status, detailMessage(await res.json().catch(() => null)));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export { detailMessage };
