import { NextIntlClientProvider, hasLocale } from "next-intl";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "../globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "LAYRA: Build Without Boundaries",
  description: "LAYRA: Towards Visual-Driven Intelligent RAG Agent",
};

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  // Ensure that the incoming `locale` is valid
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }

  return (
    <html lang={locale}>
      <body className={`${inter.className}`}>
        <NextIntlClientProvider>
          <div className="absolute w-full h-full top-0 left-0">{children}</div>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
