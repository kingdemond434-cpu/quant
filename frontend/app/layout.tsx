import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/nav";

export const metadata: Metadata = {
  title: "Quant Desk",
  description: "Quantitative research dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-bg text-fg">
        <div className="flex min-h-screen">
          <Nav />
          <main className="grid-faint min-h-screen flex-1 overflow-x-hidden">
            <div className="mx-auto max-w-[1600px] px-6 py-5">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
