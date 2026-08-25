import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * /ads.txt — AdSense publisher verification.
 *
 * Google requires a publicly accessible /ads.txt file listing authorised
 * sellers of ad inventory on the domain. The standard record format is:
 *
 *   google.com, pub-XXXXXXXXXXXXXXXX, DIRECT, f08c47fec0942fa0
 *
 * This route returns the record only when NEXT_PUBLIC_ADSENSE_CLIENT_ID is
 * configured with a real publisher ID. When unconfigured, it returns a valid
 * but empty text/plain response — search engines treat an empty ads.txt as
 * "no authorised sellers declared", which is correct before AdSense approval.
 *
 * The publisher ID is public by design (it appears in every ad request and
 * in the page source of every AdSense-enabled site), so exposing it here
 * is not a security concern.
 */
export function GET() {
  const clientId = process.env.NEXT_PUBLIC_ADSENSE_CLIENT_ID ?? "";

  // Extract the pub-XXXX portion. The env var may be "ca-pub-1234567890123456"
  // but ads.txt uses just the "pub-1234567890123456" part.
  const pubMatch = clientId.match(/pub-\d+/);

  if (!pubMatch) {
    // No valid publisher ID configured — return empty ads.txt.
    return new NextResponse("", {
      status: 200,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }

  const record = `google.com, ${pubMatch[0]}, DIRECT, f08c47fec0942fa0\n`;

  return new NextResponse(record, {
    status: 200,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
