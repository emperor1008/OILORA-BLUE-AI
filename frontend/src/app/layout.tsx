import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Oilora Blue AI — Maritime Oil-Spill Intelligence",
  description:
    "Explainable maritime oil-spill investigation and decision-support platform",
  keywords: [
    "oil spill",
    "maritime",
    "SAR",
    "satellite",
    "investigation",
    "decision support",
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
