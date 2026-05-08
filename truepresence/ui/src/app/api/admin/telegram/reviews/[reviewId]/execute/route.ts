import { proxyBackend, withRequestSearch } from "../../../../../_lib/backend";

interface ReviewExecuteRouteContext {
  params: Promise<{ reviewId: string }>;
}

export async function POST(request: Request, context: ReviewExecuteRouteContext) {
  const { reviewId } = await context.params;
  return proxyBackend(
    withRequestSearch(`/telegram/reviews/${encodeURIComponent(reviewId)}/execute`, request),
    { method: "POST", request },
  );
}
