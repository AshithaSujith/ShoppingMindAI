import type { Metadata } from "next";
import "./globals.css";


export const metadata: Metadata = {
  title: "ShoppingMind AI",
  description: "AI-powered product discovery and price comparison.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning className="h-full">
      <body className="h-full antialiased overflow-hidden">{children}</body>
    </html>
  );
}
