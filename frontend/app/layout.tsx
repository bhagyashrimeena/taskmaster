import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Wealth Copilot — What matters today",
  description: "Portfolio-aware intelligence that filters what deserves your attention.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
