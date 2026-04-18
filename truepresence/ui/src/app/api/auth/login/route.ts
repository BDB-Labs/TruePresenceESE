import { NextResponse } from "next/server";

interface LoginPayload {
  access_token?: string;
  token_type?: string;
  user?: unknown;
  detail?: string;
}

function apiBaseUrl() {
  return (
    process.env.TRUEPRESENCE_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "https://verify.bageltech.net"
  ).replace(/\/$/, "");
}

export async function POST(request: Request) {
  const credentials = await request.json();
  const upstream = await fetch(`${apiBaseUrl()}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credentials),
    cache: "no-store",
  });
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
