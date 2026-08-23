import type { Metadata, Viewport } from "next";
import { AppShell } from "@/components/shell/app-shell";
import { ProductProviders } from "@/components/providers/product-providers";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Wealth Copilot — What matters today",
    template: "%s — Wealth Copilot",
  },
  description: "Portfolio-aware intelligence that filters what deserves your attention.",
  applicationName: "Wealth Copilot",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Wealth Copilot",
  },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  interactiveWidget: "resizes-content",
  themeColor: "#185744",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <ProductProviders>
          <AppShell>{children}</AppShell>
        </ProductProviders>
      </body>
    </html>
  );
}
