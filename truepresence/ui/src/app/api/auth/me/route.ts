import { proxyBackend } from "../../_lib/backend";

export async function GET() {
  return proxyBackend("/auth/me");
}
