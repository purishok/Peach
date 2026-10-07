import { describe, expect, it } from "vitest";

import { cognitoLogoutUrl, oidcSettings } from "@/lib/oidc";

describe("OIDC configuration", () => {
  it("uses authorization code flow with the requested scopes", () => {
    expect(oidcSettings.response_type).toBe("code");
    expect(oidcSettings.scope).toBe("openid email profile");
    expect(oidcSettings.client_id).toBe("test-client");
  });

  it("constructs Cognito logout with encoded allow-listed parameters", () => {
    const url = cognitoLogoutUrl();
    expect(url.origin).toBe(
      "https://peach-test.auth.us-east-1.amazoncognito.com",
    );
    expect(url.pathname).toBe("/logout");
    expect(url.searchParams.get("client_id")).toBe("test-client");
    expect(url.searchParams.get("logout_uri")).toBe("https://example.test/");
  });
});
