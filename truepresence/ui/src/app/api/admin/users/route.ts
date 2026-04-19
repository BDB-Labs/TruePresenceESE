import { proxyBackend } from "../../_lib/backend";

export async function GET() {
  return proxyBackend("/auth/users");
}

export async function POST(request: Request) {
  return proxyBackend("/auth/users", { method: "POST", request });
}
