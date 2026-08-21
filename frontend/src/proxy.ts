import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

export function proxy(request: NextRequest) {
  if (process.env.ENVIRONMENT !== "production" || !process.env.ADMIN_USERNAME || !process.env.ADMIN_PASSWORD) return NextResponse.next();
  const authorization = request.headers.get("authorization");
  if (authorization?.startsWith("Basic ")) {
    const [username, password] = atob(authorization.slice(6)).split(":");
    if (username === process.env.ADMIN_USERNAME && password === process.env.ADMIN_PASSWORD) return NextResponse.next();
  }
  return new NextResponse("Authentication required", { status: 401, headers: { "WWW-Authenticate": 'Basic realm="JobsVsAI data console"' } });
}
export const config = { matcher: ["/admin/:path*"] };
