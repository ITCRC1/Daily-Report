import type { Metadata } from "next";
import { Manrope } from "next/font/google";
import "./globals.css";

// Manrope es la tipografia de glif (`--font-glif-sans`). Se carga con
// `next/font` y no con un <link>: queda auto-hospedada, sin pedido a Google en
// cada visita y sin el salto de linea-base que produce una fuente que llega
// tarde -- en una tabla de once columnas ese salto se ve como un temblor.
//
// `variable` la expone como `--font-sans`, que es de donde la toma Tailwind.
const manrope = Manrope({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans",
});
import TopNav from "@/components/TopNav";

export const metadata: Metadata = {
  title: "DAILY-OPS · Corcovado Wilderness Lodge",
  description: "Daily/weekly revenue, cash, and daily audit",
};

// El app no tiene login: se entra directo al dashboard.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={manrope.variable}>
      <body>
        <TopNav />
        <main className="mx-auto max-w-6xl px-5 py-6">{children}</main>
      </body>
    </html>
  );
}
