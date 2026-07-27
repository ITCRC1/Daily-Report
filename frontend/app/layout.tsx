import type { Metadata } from "next";
import "./globals.css";
import TopNav from "@/components/TopNav";

export const metadata: Metadata = {
  title: "DAILY-OPS · Corcovado Wilderness Lodge",
  description: "Daily/weekly revenue, cash, and daily audit",
};

// El app no tiene login: se entra directo al dashboard.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <TopNav />
        <main className="mx-auto max-w-6xl px-5 py-6">{children}</main>
      </body>
    </html>
  );
}
