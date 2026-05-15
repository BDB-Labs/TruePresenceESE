import { proxyBackend, withRequestSearch } from "../../_lib/backend";

const EVIDENCE_CARDS_PATH = "/api/v1/truepresence/evidence/cards";

export async function GET(request: Request) {
  return proxyBackend(withRequestSearch(EVIDENCE_CARDS_PATH, request), { request });
}
