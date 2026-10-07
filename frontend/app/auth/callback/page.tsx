"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "react-oidc-context";

import { Button } from "@/components/ui/button";
import { getUserManager } from "@/lib/oidc";

const CALLBACK_TIMEOUT_MS = 20_000;

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown sign-in error.";
}

export default function AuthCallbackPage() {
  const auth = useAuth();
  const router = useRouter();
  const started = useRef(false);
  const [callbackError, setCallbackError] = useState<string | null>(null);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    const callbackUrl = window.location.href;
    const params = new URL(callbackUrl).searchParams;
    const hasResponse =
      params.has("state") && (params.has("code") || params.has("error"));

    if (!hasResponse) {
      queueMicrotask(() => {
        setCallbackError(
          "The sign-in response is missing its authorization code or state. Start sign in again.",
        );
      });
      return;
    }

    let completed = false;
    const timeout = window.setTimeout(() => {
      if (!completed) {
        setCallbackError(
          "Sign in is taking too long to complete. Check your connection and start again.",
        );
      }
    }, CALLBACK_TIMEOUT_MS);

    void getUserManager()
      .signinRedirectCallback(callbackUrl)
      .then((user) => {
        if (!user) throw new Error("Cognito did not return a signed-in user.");
        completed = true;
        window.clearTimeout(timeout);
        window.history.replaceState({}, document.title, "/auth/callback");
        router.replace("/home");
      })
      .catch((error: unknown) => {
        completed = true;
        window.clearTimeout(timeout);
        setCallbackError(errorMessage(error));
      });
  }, [router]);

  const displayedError = callbackError ?? auth.error?.message;

  if (displayedError) {
    return (
      <main className="flex flex-1 items-center justify-center px-6">
        <section className="w-full max-w-md text-center">
          <h1 className="font-heading text-2xl font-bold">
            Could not complete sign in
          </h1>
          <p role="alert" className="mt-3 text-sm text-destructive">
            {displayedError}
          </p>
          <Button asChild className="mt-6">
            <Link href="/login">Start again</Link>
          </Button>
        </section>
      </main>
    );
  }

  return (
    <main className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
      Completing secure sign in…
    </main>
  );
}
