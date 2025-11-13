import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Legal Multi-Agent Workspace",
  description: "Secure chat for legal teams with multi-agent synthesis",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-100">
        <div className="mx-auto flex min-h-screen max-w-6xl gap-6 p-6">{children}</div>
      </body>
    </html>
  );
}
