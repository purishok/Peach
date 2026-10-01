"use client";

import * as React from "react";

const STORAGE_KEY = "peach-local-demo-session";
const DEMO_MODE = process.env.NEXT_PUBLIC_LOCAL_DEMO_MODE === "true";
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Session = {
  email: string;
  name: string;
  token: string;
};

type AuthReply = {
  access_token: string;
  user: { email: string; name: string };
};

function readSession(): Session | null {
  if (!DEMO_MODE || typeof window === "undefined") return null;
  try {
    const value: unknown = JSON.parse(
      localStorage.getItem(STORAGE_KEY) ?? "null",
    );
    if (
      typeof value === "object" &&
      value !== null &&
      "email" in value &&
      typeof value.email === "string" &&
      "name" in value &&
      typeof value.name === "string" &&
      "token" in value &&
      typeof value.token === "string"
    ) {
      return { email: value.email, name: value.name, token: value.token };
    }
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
  return null;
}

async function authenticate(
  path: "signup" | "login",
  payload: { email: string; password: string; name?: string },
): Promise<{ session: Session | null; error?: string }> {
  if (!DEMO_MODE) return { session: null, error: "Local sign-in is disabled." };
  try {
    const response = await fetch(`${API_URL}/auth/local/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = (await response.json()) as AuthReply & { detail?: string };
    if (!response.ok) {
      return { session: null, error: body.detail ?? "Could not sign in." };
    }
    const session = {
      email: body.user.email,
      name: body.user.name,
      token: body.access_token,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    window.dispatchEvent(new Event("peach-session-change"));
    return { session };
  } catch {
    return {
      session: null,
      error: "Could not reach the API. Is Docker Compose running?",
    };
  }
}

export function signInDemo(email: string, password: string) {
  return authenticate("login", { email: email.trim().toLowerCase(), password });
}

export function signUpDemo(name: string, email: string, password: string) {
  return authenticate("signup", {
    name: name.trim(),
    email: email.trim().toLowerCase(),
    password,
  });
}

export function getIdToken(): string | null {
  return readSession()?.token ?? null;
}

export function signOut(): void {
  localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new Event("peach-session-change"));
}

export function useSession(): Session | null | undefined {
  const [session, setSession] = React.useState<Session | null | undefined>(
    undefined,
  );
  React.useEffect(() => {
    const update = () => setSession(readSession());
    update();
    window.addEventListener("storage", update);
    window.addEventListener("peach-session-change", update);
    return () => {
      window.removeEventListener("storage", update);
      window.removeEventListener("peach-session-change", update);
    };
  }, []);
  return session;
}
