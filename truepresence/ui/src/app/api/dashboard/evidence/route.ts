import { proxyBackend, withRequestSearch } from "../../_lib/backend";

export async function GET(request: Request) {
  return proxyBackend(withRequestSearch("/v1/truepresence/evidence/cards", request));
}
