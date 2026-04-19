import { proxyBackend, withRequestSearch } from "../../../_lib/backend";

export async function GET(request: Request) {
  return proxyBackend(withRequestSearch("/telegram/config", request));
}

export async function POST(request: Request) {
  return proxyBackend(withRequestSearch("/telegram/config/detectors", request), {
    method: "POST",
    request,
  });
}
