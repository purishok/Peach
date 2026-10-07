"use client";

import { useAuth } from "react-oidc-context";

import { cognitoLogoutUrl, getUserManager } from "@/lib/oidc";

export type Session = {
  email: string;
  name: string;
};

/** Compatibility helper for the already-protected API in this repository.
 * The backend currently validates Cognito ID tokens specifically. A future
 * access-token migration can use `useAuth().user?.access_token` instead. */
export async function getIdToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  return (await getUserManager().getUser())?.id_token ?? null;
}

/** Clear local OIDC state first, then end the Cognito browser session. */
export async function signOut(): Promise<void> {
  if (typeof window === "undefined") return;
  const manager = getUserManager();
  await manager.removeUser();
  window.location.assign(cognitoLogoutUrl());
}

export function useSession(): Session | null | undefined {
  const auth = useAuth();
  if (auth.isLoading || auth.activeNavigator) return undefined;
  if (!auth.isAuthenticated || !auth.user) return null;

  const email =
    typeof auth.user.profile.email === "string"
      ? auth.user.profile.email
      : "Signed-in user";
  const name =
    typeof auth.user.profile.name === "string" ? auth.user.profile.name : email;
  return { email, name };
}
