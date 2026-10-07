"use client";

import { UserManager, WebStorageStateStore } from "oidc-client-ts";

const authority = process.env.NEXT_PUBLIC_COGNITO_AUTHORITY ?? "";
const clientId = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID ?? "";
const domain = process.env.NEXT_PUBLIC_COGNITO_DOMAIN ?? "";
const redirectUri = process.env.NEXT_PUBLIC_COGNITO_REDIRECT_URI ?? "";
const logoutUri = process.env.NEXT_PUBLIC_COGNITO_LOGOUT_URI ?? "";

export const oidcSettings = {
  authority,
  client_id: clientId,
  redirect_uri: redirectUri,
  response_type: "code",
  scope: "openid email profile",
  loadUserInfo: false,
  automaticSilentRenew: true,
  monitorSession: false,
} as const;

export function oidcConfigurationError(): string | null {
  const missing = [
    ["NEXT_PUBLIC_COGNITO_AUTHORITY", authority],
    ["NEXT_PUBLIC_COGNITO_CLIENT_ID", clientId],
    ["NEXT_PUBLIC_COGNITO_DOMAIN", domain],
    ["NEXT_PUBLIC_COGNITO_REDIRECT_URI", redirectUri],
    ["NEXT_PUBLIC_COGNITO_LOGOUT_URI", logoutUri],
  ]
    .filter(([, value]) => !value)
    .map(([name]) => name);

  return missing.length > 0
    ? `Authentication is not configured (${missing.join(", ")}).`
    : null;
}

let userManager: UserManager | undefined;

export function getUserManager(): UserManager {
  const configurationError = oidcConfigurationError();
  if (configurationError) throw new Error(configurationError);

  userManager ??= new UserManager(
    typeof window === "undefined"
      ? oidcSettings
      : {
          ...oidcSettings,
          userStore: new WebStorageStateStore({ store: window.localStorage }),
          stateStore: new WebStorageStateStore({ store: window.sessionStorage }),
        },
  );
  return userManager;
}

export function cognitoLogoutUrl(): URL {
  const url = new URL("/logout", domain);
  url.searchParams.set("client_id", clientId);
  url.searchParams.set("logout_uri", logoutUri);
  return url;
}
