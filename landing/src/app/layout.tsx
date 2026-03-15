import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "memable — Memory for AI Agents",
  description: "Production-grade semantic memory for AI agents. Python, TypeScript, and MCP support. Open source.",
  openGraph: {
    title: "memable — Memory for AI Agents",
    description: "Production-grade semantic memory for AI agents. Works everywhere.",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "memable — Memory for AI Agents",
    description: "Production-grade semantic memory for AI agents. Works everywhere.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
