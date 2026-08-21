import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

// Container liveness for the Next.js process only. It deliberately does not call the API:
// a backend blip should not make the web tier look dead and get restarted underneath a
// reverse proxy. Backend and database health are reported by the API's own /health.
export function GET() {
  return NextResponse.json({ status: "ok", service: "frontend" });
}
