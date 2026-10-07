import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AuthCallbackPage from "@/app/auth/callback/page";
import LoginPage from "@/app/login/page";

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  signinRedirect: vi.fn(async () => {}),
  signinRedirectCallback: vi.fn(),
  useAuth: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mocks.replace }),
}));

vi.mock("react-oidc-context", () => ({
  useAuth: mocks.useAuth,
}));

vi.mock("@/lib/oidc", () => ({
  getUserManager: () => ({
    signinRedirectCallback: mocks.signinRedirectCallback,
  }),
}));

describe("Cognito redirect flow", () => {
  beforeEach(() => {
    mocks.replace.mockReset();
    mocks.signinRedirect.mockClear();
    mocks.signinRedirectCallback.mockReset();
    mocks.signinRedirectCallback.mockResolvedValue({
      profile: { email: "person@example.test" },
    });
    window.history.replaceState({}, "", "/");
    mocks.useAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      activeNavigator: undefined,
      error: undefined,
      signinRedirect: mocks.signinRedirect,
    });
  });

  it("starts one library-managed redirect from /login", async () => {
    const view = render(<LoginPage />);
    await waitFor(() => expect(mocks.signinRedirect).toHaveBeenCalledOnce());

    view.rerender(<LoginPage />);
    expect(mocks.signinRedirect).toHaveBeenCalledOnce();
    expect(screen.getByText(/Redirecting to secure sign in/)).toBeVisible();
  });

  it("exchanges the callback code once, cleans the URL, and opens home", async () => {
    window.history.replaceState(
      {},
      "",
      "/auth/callback?code=authorization-code&state=stored-state",
    );

    const view = render(<AuthCallbackPage />);
    await waitFor(() =>
      expect(mocks.signinRedirectCallback).toHaveBeenCalledWith(
        "http://localhost:3000/auth/callback?code=authorization-code&state=stored-state",
      ),
    );
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/home"));

    view.rerender(<AuthCallbackPage />);
    expect(mocks.signinRedirectCallback).toHaveBeenCalledOnce();
    expect(window.location.pathname).toBe("/auth/callback");
    expect(window.location.search).toBe("");
  });

  it("shows callback errors instead of waiting indefinitely", async () => {
    window.history.replaceState(
      {},
      "",
      "/auth/callback?code=authorization-code&state=stored-state",
    );
    mocks.signinRedirectCallback.mockRejectedValue(
      new Error("No matching state found in storage"),
    );

    render(<AuthCallbackPage />);

    expect(
      await screen.findByText("No matching state found in storage"),
    ).toBeVisible();
    expect(mocks.replace).not.toHaveBeenCalled();
  });

  it("rejects a callback without code and state", async () => {
    window.history.replaceState({}, "", "/auth/callback");

    render(<AuthCallbackPage />);

    expect(
      await screen.findByText(/missing its authorization code or state/i),
    ).toBeVisible();
    expect(mocks.signinRedirectCallback).not.toHaveBeenCalled();
  });
});
