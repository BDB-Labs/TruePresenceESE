import { NextResponse } from "next/server";

import {
  configuredApiBaseUrl,
  missingBackendConfigResponse,
} from "../../_lib/backend";

interface LoginPayload {
  access_token?: string;
  token_type?: string;
  user?: unknown;
  detail?: string;
}

export async function POST(request: Request) {
  const baseUrl = configuredApiBaseUrl();
  if (!baseUrl) {
    return missingBackendConfigResponse();
  }

  let credentials: Record<string, unknown>;
  try {
    credentials = await request.json();
  } catch {
    return NextResponse.json({ detail: "Request body must be valid JSON" }, { status: 400 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${baseUrl}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credentials),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { detail: "TruePresence backend is unavailable" },
      { status: 502 },
    );
  }
  const payload = (await upstream.json()) as LoginPayload;

  if (!upstream.ok || !payload.access_token) {
    return NextResponse.json(
      { detail: payload.detail || "Invalid credentials" },
      { status: upstream.status },
    );
  }

  const response = NextResponse.json({
    token_type: payload.token_type || "bearer",
    user: payload.user,
  });
  response.cookies.set("truepresence_token", payload.access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24,
  });
  return response;
}
