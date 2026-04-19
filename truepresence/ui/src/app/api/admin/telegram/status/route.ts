import { proxyBackend, withRequestSearch } from "../../../_lib/backend";

export async function GET(request: Request) {
  return proxyBackend(withRequestSearch("/telegram/status", request));
}
