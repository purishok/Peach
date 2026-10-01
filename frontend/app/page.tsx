"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { signInDemo, useSession } from "@/lib/auth";

export default function Page() {
  const router = useRouter();
  const session = useSession();
  const [email, setEmail] = useState("demo@peach.local");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (session) router.replace("/home");
  }, [session, router]);

  async function continueToApp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = await signInDemo(email, password);
    if (!result.session) {
      setError(result.error ?? "Could not sign in.");
      return;
    }
    router.push("/home");
  }

  return (
    <main className="flex flex-1 flex-col items-center px-6 pt-[14vh] pb-12">
      <section className="w-full max-w-[320px]">
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
          Log in to your Peach workspace
        </p>
        <form className="grid gap-4" onSubmit={continueToApp}>
          <Field>
            <FieldLabel htmlFor="email">Email</FieldLabel>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="Enter your email address..."
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="password">Password</FieldLabel>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              placeholder="Enter your password..."
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </Field>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <Button type="submit" className="w-full" size="lg">
            Continue
          </Button>
        </form>
        <p className="mt-8 text-center text-sm text-muted-foreground">
          Don&apos;t have an account?{" "}
          <a
            className="font-medium text-primary hover:underline"
            href="/signup"
          >
            Sign up
          </a>
        </p>
      </section>
    </main>
  );
}
