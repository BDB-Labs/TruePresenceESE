import { proxyBackend, withRequestSearch } from "../../../../_lib/backend";

interface ReviewRouteContext {
  params: Promise<{ reviewId: string }>;
}

export async function GET(request: Request, context: ReviewRouteContext) {
  const { reviewId } = await context.params;
  return proxyBackend(
    withRequestSearch(`/telegram/reviews/${encodeURIComponent(reviewId)}`, request),
  );
}
