import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Data Analyst Agent",
  description: "Upload-first UI for dataset ingestion and analysis job submission."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
