import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy | Peach",
  description: "How Peach uses account information for authentication.",
};

export default function PrivacyPolicyPage() {
  return (
    <main className="mx-auto w-full max-w-2xl flex-1 px-6 py-12 sm:px-8 sm:py-16">
      <Link
        href="/"
        className="text-sm font-medium text-primary hover:underline"
      >
        ← Back to Peach
      </Link>

      <article className="mt-8">
        <h1 className="font-heading text-3xl font-bold sm:text-4xl">
          Privacy Policy
        </h1>

        <div className="mt-8 space-y-5 text-base leading-7 text-muted-foreground">
          <p>
            Peach uses Google Sign-In and Amazon Cognito only to authenticate
            users.
          </p>
          <p>
            We access basic account information such as your name, email
            address, and profile information required for authentication.
          </p>
          <p>
            We do not sell Google user data or share it with third parties for
            advertising purposes.
          </p>
          <p>
            Authentication is handled through Amazon Cognito and Google OAuth.
          </p>
          <p>
            For questions about this policy, contact the Peach project
            maintainer through the project&apos;s usual support channel.
          </p>
        </div>
      </article>
    </main>
  );
}
