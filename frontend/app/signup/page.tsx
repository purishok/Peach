"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { signUpDemo, useSession } from "@/lib/auth";

export default function SignUpPage() {
  const router = useRouter();
  const session = useSession();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (session) router.replace("/home");
  }, [session, router]);

  async function createWorkspace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== confirmation) {
      setError("Passwords do not match.");
      return;
    }
    const result = await signUpDemo(name, email, password);
    if (!result.session) {
      setError(result.error ?? "Could not create your account.");
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
          Create your account
        </h1>
        <p className="mt-1 mb-8 text-[1.05rem] font-medium text-muted-foreground">
          Start tracking work in Peach
        </p>
        <form className="grid gap-4" onSubmit={createWorkspace}>
          <Field>
            <FieldLabel htmlFor="name">Name</FieldLabel>
            <Input
              id="name"
              autoComplete="name"
              placeholder="What should we call you?"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
              maxLength={200}
            />
          </Field>
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
              autoComplete="new-password"
              placeholder="At least 8 characters"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={8}
              maxLength={128}
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="confirm">Confirm password</FieldLabel>
            <Input
              id="confirm"
              type="password"
              autoComplete="new-password"
              placeholder="Type it again"
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              required
              minLength={8}
              maxLength={128}
            />
          </Field>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <Button type="submit" className="w-full" size="lg">
            Create account
          </Button>
        </form>
        <p className="mt-8 text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link className="font-medium text-primary hover:underline" href="/">
            Log in
          </Link>
        </p>
      </section>
    </main>
  );
}
