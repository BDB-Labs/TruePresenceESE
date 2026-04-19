import { cookies } from "next/headers";
import { NextResponse } from "next/server";

interface ProxyOptions {
  method?: string;
  request?: Request;
}

export function apiBaseUrl() {
  return (
    process.env.TRUEPRESENCE_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "https://verify.bageltech.net"
  ).replace(/\/$/, "");
}

export function withRequestSearch(path: string, request: Request) {
  const search = new URL(request.url).search;
  return `${path}${search}`;
}

async function authToken() {
  const cookieStore = await cookies();
  return cookieStore.get("truepresence_token")?.value;
}

async function responseFromUpstream(upstream: Response) {
  if (upstream.status === 204) {
    return new NextResponse(null, { status: 204 });
  }

  const contentType = upstream.headers.get("content-type") || "";
  const text = await upstream.text();

  if (!text) {
    return NextResponse.json(null, { status: upstream.status });
  }

  if (contentType.includes("application/json")) {
    try {
      return NextResponse.json(JSON.parse(text), { status: upstream.status });
    } catch {
      return NextResponse.json(
        { detail: "Backend returned invalid JSON" },
        { status: 502 },
      );
    }
  }

  return new NextResponse(text, {
    status: upstream.status,
    headers: { "Content-Type": contentType || "text/plain" },
  });
}

export async function proxyBackend(path: string, options: ProxyOptions = {}) {
  const token = await authToken();
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const method = options.method || options.request?.method || "GET";
  const headers = new Headers({
    Accept: "application/json",
    Authorization: `Bearer ${token}`,
  });
  let body: string | undefined;

  if (options.request && method !== "GET" && method !== "HEAD") {
    body = await options.request.text();
    if (body) {
      headers.set(
        "Content-Type",
        options.request.headers.get("content-type") || "application/json",
      );
    }
  }

  try {
    const upstream = await fetch(`${apiBaseUrl()}${path}`, {
      method,
      headers,
      body,
      cache: "no-store",
    });
    return responseFromUpstream(upstream);
  } catch (error) {
    console.error("Backend proxy failed", error);
    return NextResponse.json(
      { detail: "TruePresence backend is unavailable" },
      { status: 502 },
    );
  }
}
