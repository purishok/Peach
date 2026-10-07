"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { useSession } from "@/lib/auth";

export default function Page() {
  const router = useRouter();
  const session = useSession();

  useEffect(() => {
    if (session) router.replace("/home");
  }, [session, router]);

  return (
    <>
      <SiteHeader />
      <main className="flex flex-1 flex-col items-center px-6 pt-[14vh] pb-12">
        <section className="w-full max-w-[360px]">
          <span
            aria-hidden="true"
            className="grid size-10 place-items-center rounded-lg bg-foreground font-heading text-lg leading-none font-semibold text-background"
          >
            P
          </span>
          <h1 className="mt-6 font-heading text-[1.75rem] leading-tight font-bold">
            Think it. Track it.
          </h1>
          <p className="mt-1 mb-8 text-[1.05rem] font-medium text-muted-foreground">
            Sign in securely to your Peach workspace.
          </p>
          <Button asChild className="w-full" size="lg">
            <Link href="/login">Sign in or create an account</Link>
          </Button>
          <p className="mt-4 text-center text-sm text-muted-foreground">
            Email/password and Google sign-in are handled by Amazon Cognito.
          </p>
        </section>
      </main>
    </>
  );
}
