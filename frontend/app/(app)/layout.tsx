"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { SiteHeader } from "@/components/site-header";
import { useSession } from "@/lib/auth";

export default function AppLayout({ children }: LayoutProps<"/">) {
  const session = useSession();
  const router = useRouter();

  useEffect(() => {
    if (session === null) router.replace("/");
  }, [session, router]);

  if (!session) {
    return (
      <main className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
        Loading Peach…
      </main>
    );
  }

  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-10 sm:px-8">
        {children}
      </main>
    </>
  );
}
