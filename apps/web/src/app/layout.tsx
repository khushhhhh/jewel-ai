import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Jewel AI — AI-Powered Jewelry Enhancement",
  description: "Transform jewelry photography with AI-powered background generation, defect cleanup, and detail enhancement. Professional e-commerce quality in seconds.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
