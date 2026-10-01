"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { api, itemStatuses } from "@/lib/api";
import { statusMeta } from "@/lib/item-status";

export function TaskDashboard() {
  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ["items"],
    queryFn: () => api.listItems({ limit: 100 }),
  });
  const complete =
    data?.items.filter((item) => item.status === "done").length ?? 0;
  const progress = data?.total ? Math.round((complete / data.total) * 100) : 0;

  return (
    <div className="grid gap-8">
      <PageHeader
        icon="📊"
        title="Home"
        description={
          isPending
            ? "Loading your workspace…"
            : `${data?.total ?? 0} tasks in your workspace`
        }
        action={
          <Button asChild>
            <Link href="/items">Open board</Link>
          </Button>
        }
      />
      {isError && (
        <Alert variant="destructive">
          <AlertTitle>Could not load your workspace</AlertTitle>
          <AlertDescription className="flex items-center gap-4">
            <span>{(error as Error).message}</span>
            <Button size="sm" variant="outline" onClick={() => refetch()}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {data && (
        <>
          <section className="grid gap-4 sm:grid-cols-2">
            <article className="rounded-xl border bg-card p-6 shadow-notion-xs">
              <p className="text-sm text-muted-foreground">Tasks completed</p>
              <p className="mt-2 font-heading text-4xl font-bold">
                {progress}%
              </p>
              <div
                className="mt-4 h-2 overflow-hidden rounded-full bg-muted"
                role="progressbar"
                aria-label="Tasks completed"
                aria-valuenow={progress}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div
                  className="h-full rounded-full bg-primary transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                {complete} of {data.total} tasks done
              </p>
            </article>
            <article className="rounded-xl border bg-card p-6 shadow-notion-xs">
              <p className="text-sm text-muted-foreground">By status</p>
              <div
                className="mt-5 flex h-3 overflow-hidden rounded-full bg-muted"
                aria-label="Tasks by status"
              >
                {itemStatuses.map((status) => {
                  const count = data.items.filter(
                    (item) => item.status === status,
                  ).length;
                  return (
                    <div
                      key={status}
                      className={statusMeta[status].mark}
                      style={{
                        width: data.total
                          ? `${(count / data.total) * 100}%`
                          : "0%",
                      }}
                      title={`${statusMeta[status].label}: ${count}`}
                    />
                  );
                })}
              </div>
              <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-xs text-muted-foreground">
                {itemStatuses.map((status) => (
                  <span
                    key={status}
                    className="inline-flex items-center gap-1.5"
                  >
                    <span
                      aria-hidden
                      className={`size-2 rounded-full ${statusMeta[status].mark}`}
                    />
                    {statusMeta[status].label} ·{" "}
                    {data.items.filter((item) => item.status === status).length}
                  </span>
                ))}
              </div>
            </article>
          </section>
          <section className="grid gap-3 sm:grid-cols-3">
            {itemStatuses.map((status) => {
              const count = data.items.filter(
                (item) => item.status === status,
              ).length;
              return (
                <Link
                  key={status}
                  href="/items"
                  className="rounded-xl border bg-card p-5 shadow-notion-xs transition hover:shadow-notion-sm"
                >
                  <span className="flex items-center justify-between text-sm text-muted-foreground">
                    {statusMeta[status].label}
                    <span
                      aria-hidden
                      className={`size-2.5 rounded-full ${statusMeta[status].mark}`}
                    />
                  </span>
                  <span className="mt-2 block font-heading text-3xl font-semibold">
                    {count}
                  </span>
                  <span className="mt-1 block text-xs text-muted-foreground">
                    View on board →
                  </span>
                </Link>
              );
            })}
          </section>
          <section className="rounded-xl border bg-card p-6 shadow-notion-xs">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="font-heading text-lg font-semibold">
                  Recently updated
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Your latest changes across the board
                </p>
              </div>
              <Link
                className="text-sm font-medium text-primary hover:underline"
                href="/items"
              >
                View all
              </Link>
            </div>
            {data.items.length === 0 ? (
              <p className="mt-5 rounded-lg bg-muted/70 px-4 py-6 text-center text-sm text-muted-foreground">
                No tasks yet. Create your first one on the board.
              </p>
            ) : (
              <ul className="mt-4 divide-y">
                {[...data.items]
                  .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
                  .slice(0, 5)
                  .map((item) => (
                    <li
                      key={item.id}
                      className="flex items-center justify-between gap-4 py-3"
                    >
                      <span className="truncate text-sm font-medium">
                        {item.name}
                      </span>
                      <span
                        className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${statusMeta[item.status].pill}`}
                      >
                        {statusMeta[item.status].label}
                      </span>
                    </li>
                  ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
