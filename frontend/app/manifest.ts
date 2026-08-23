import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Wealth Copilot",
    short_name: "Wealth Copilot",
    description: "Portfolio-aware intelligence for what deserves your attention next.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#f6f7f3",
    theme_color: "#185744",
    orientation: "portrait-primary",
    categories: ["finance", "productivity"],
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
    ],
    shortcuts: [
      { name: "Portfolio", short_name: "Portfolio", url: "/portfolio" },
      { name: "Alerts", short_name: "Alerts", url: "/alerts" },
      { name: "Copilot", short_name: "Copilot", url: "/copilot" },
    ],
  };
}
