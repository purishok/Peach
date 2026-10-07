"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function SignUpPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/login");
  }, [router]);

  return (
    <main className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
      Redirecting to secure sign up…
    </main>
  );
}
