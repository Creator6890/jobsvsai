import { ImageResponse } from "next/og";

export const size = { width: 64, height: 64 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "white", background: "linear-gradient(135deg, #6d28d9, #a855f7)", borderRadius: 14, fontSize: 27, fontWeight: 900, letterSpacing: -2 }}>vs</div>,
    size,
  );
}
