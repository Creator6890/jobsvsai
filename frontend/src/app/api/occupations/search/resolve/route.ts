import { NextRequest, NextResponse } from "next/server";
import { ApiError, resolveOccupationSearch } from "@/lib/api";

/** Search with the outcome made explicit.
 *
 *  Distinguishes "we could not understand that" from "that occupation exists but we have not
 *  published an analysis for it". Collapsing the two is what let the old search answer
 *  "pen tester" with Non-Destructive Testing Specialists. */
export async function GET(request: NextRequest) {
  const query = request.nextUrl.searchParams.get("q")?.trim() ?? "";
  if (query.length < 2) {
    return NextResponse.json({ queryStatus: "no_reliable_match", results: [] });
  }
  try {
    return NextResponse.json(await resolveOccupationSearch(query));
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 503;
    return NextResponse.json(
      { detail: "Occupation search is temporarily unavailable" },
      { status },
    );
  }
}
