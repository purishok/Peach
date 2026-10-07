"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { useAuth } from "react-oidc-context";

import { Button } from "@/components/ui/button";

export default function LoginPage() {
  const auth = useAuth();
  const router = useRouter();
  const started = useRef(false);

  useEffect(() => {
    if (auth.isAuthenticated) {
      router.replace("/home");
      return;
    }
    if (
      !auth.isLoading &&
      !auth.activeNavigator &&
      !auth.error &&
      !started.current
    ) {
      started.current = true;
      void auth.signinRedirect();
    }
  }, [auth, router]);

  if (auth.error) {
    return (
      <main className="flex flex-1 items-center justify-center px-6">
        <section className="w-full max-w-md text-center">
          <h1 className="font-heading text-2xl font-bold">Sign-in failed</h1>
          <p role="alert" className="mt-3 text-sm text-destructive">
            {auth.error.message}
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Button
              onClick={() => {
                started.current = true;
                void auth.signinRedirect();
              }}
            >
              Try again
            </Button>
            <Button asChild variant="outline">
              <Link href="/">Back to Peach</Link>
            </Button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
      Redirecting to secure sign in…
    </main>
  );
}
