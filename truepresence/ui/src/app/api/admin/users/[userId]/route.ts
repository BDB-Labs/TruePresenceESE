import { proxyBackend } from "../../../_lib/backend";

interface UserRouteContext {
  params: Promise<{ userId: string }>;
}

export async function PATCH(request: Request, context: UserRouteContext) {
  const { userId } = await context.params;
  return proxyBackend(`/auth/users/${encodeURIComponent(userId)}`, {
    method: "PATCH",
    request,
  });
}

export async function DELETE(_request: Request, context: UserRouteContext) {
  const { userId } = await context.params;
  return proxyBackend(`/auth/users/${encodeURIComponent(userId)}`, {
    method: "DELETE",
  });
}
