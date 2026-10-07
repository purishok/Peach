"use client";

import { useState, type ReactNode } from "react";
import { AuthProvider } from "react-oidc-context";
import type { UserManager } from "oidc-client-ts";

import { getUserManager, oidcConfigurationError } from "@/lib/oidc";

export function PeachAuthProvider({ children }: { children: ReactNode }) {
  const configurationError = oidcConfigurationError();
  const [manager] = useState<UserManager | null>(() =>
    configurationError ? null : getUserManager(),
  );

  if (configurationError) {
    return (
      <main className="flex flex-1 items-center justify-center px-6 text-center text-sm text-destructive">
        {configurationError}
      </main>
    );
  }

  if (!manager) return null;

  return (
    <AuthProvider userManager={manager} skipSigninCallback>
      {children}
    </AuthProvider>
  );
}
