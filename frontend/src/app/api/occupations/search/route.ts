import { NextRequest, NextResponse } from "next/server";
import { ApiError, searchOccupations } from "@/lib/api";

export async function GET(request: NextRequest) {
  const query = request.nextUrl.searchParams.get("q")?.trim() ?? "";
  if (query.length < 2) return NextResponse.json([]);
  try {
    return NextResponse.json(await searchOccupations(query));
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 503;
    return NextResponse.json({ detail: "Occupation search is temporarily unavailable" }, { status });
  }
}
