import { proxyBackend, withRequestSearch } from "../../../../../_lib/backend";

interface ReviewResolveRouteContext {
  params: Promise<{ reviewId: string }>;
}

export async function POST(request: Request, context: ReviewResolveRouteContext) {
  const { reviewId } = await context.params;
  return proxyBackend(
    withRequestSearch(`/telegram/reviews/${encodeURIComponent(reviewId)}/resolve`, request),
    { method: "POST", request },
  );
}
