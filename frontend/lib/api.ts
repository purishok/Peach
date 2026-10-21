import { z } from "zod";

import { getIdToken, signOut } from "@/lib/auth";

/** Browser code must reach the API through the published port; server components
 *  resolve the Compose service name instead. */
export function apiBaseUrl(): string {
  if (typeof window === "undefined") {
    return process.env.INTERNAL_API_URL ?? "http://backend:8000";
  }
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  // Every API route needs a signed-in user; don't send what would bounce.
  const token = await getIdToken();
  if (!token) throw new ApiError(401, "You are signed out");

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(0, "Could not reach the API");
  }

  // The API no longer accepts this session (revoked, or the pool changed):
  // drop it, and the auth gate sends the user back to the login page.
  if (response.status === 401) signOut();

  if (!response.ok) {
    const detail = await response
      .json()
      .then((body) => (typeof body?.detail === "string" ? body.detail : null))
      .catch(() => null);
    throw new ApiError(
      response.status,
      detail ?? `Request failed (${response.status})`,
    );
  }

  if (response.status === 204) {
    return schema.parse(undefined);
  }
  return schema.parse(await response.json());
}

/* --- schemas mirroring the API contract in README section 5 --- */

export const itemStatuses = ["todo", "in_progress", "done"] as const;
export const itemStatusSchema = z.enum(itemStatuses);

export const itemSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  status: itemStatusSchema,
  created_at: z.string(),
  updated_at: z.string(),
});

export const itemListSchema = z.object({
  items: z.array(itemSchema),
  total: z.number().int(),
});

export const healthSchema = z.object({
  status: z.string(),
  database: z.string(),
});

export const itemInputSchema = z.object({
  name: z.string().min(1, "Name is required").max(120, "Name is too long"),
  description: z.string().max(2000, "Description is too long").optional(),
  status: itemStatusSchema,
});

export type ItemStatus = z.infer<typeof itemStatusSchema>;
export type Item = z.infer<typeof itemSchema>;
export type ItemList = z.infer<typeof itemListSchema>;
export type Health = z.infer<typeof healthSchema>;
export type ItemInput = z.infer<typeof itemInputSchema>;

export const agendaSchema = z.object({
  title: z.string().nullable(),
  starts_at: z.string().nullable(),
  duration_minutes: z.number().int().nullable(),
  items: z.array(
    z.object({
      topic: z.string(),
      owner: z.string().nullable(),
      minutes: z.number().int().nullable(),
    }),
  ),
  action_items: z.array(
    z.object({
      task: z.string(),
      owner: z.string().nullable(),
      due: z.string().nullable(),
    }),
  ),
  language: z.string(),
});
export type Agenda = z.infer<typeof agendaSchema>;
export const meetingSchema = z.object({
  id: z.string(),
  title: z.string(),
  starts_at: z.string(),
  ends_at: z.string(),
  agenda: agendaSchema.nullable(),
  ai_suggestion: z.unknown().nullable(),
});
export type Meeting = z.infer<typeof meetingSchema>;

/* --- endpoints --- */

export const api = {
  readiness: () => request("/api/v1/health/ready", healthSchema),

  listItems: (params: { limit?: number; offset?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.limit !== undefined) query.set("limit", String(params.limit));
    if (params.offset !== undefined) query.set("offset", String(params.offset));
    const suffix = query.size > 0 ? `?${query}` : "";
    return request(`/api/v1/items${suffix}`, itemListSchema);
  },

  createItem: (payload: ItemInput) =>
    request("/api/v1/items", itemSchema, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateItem: (id: string, payload: Partial<ItemInput>) =>
    request(`/api/v1/items/${id}`, itemSchema, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  deleteItem: (id: string) =>
    request(`/api/v1/items/${id}`, z.undefined(), { method: "DELETE" }),

  listMeetings: () =>
    request("/api/v1/meetings", z.object({ meetings: z.array(meetingSchema) })),
  createMeeting: (payload: {
    title: string;
    starts_at: string;
    ends_at: string;
  }) =>
    request("/api/v1/meetings", meetingSchema, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  saveAgenda: (id: string, agenda: Agenda, ai_suggestion: unknown) =>
    request(`/api/v1/meetings/${id}/agenda`, meetingSchema, {
      method: "PUT",
      body: JSON.stringify({ agenda, ai_suggestion }),
    }),
};

const parseSchema = z.object({
  agenda: agendaSchema,
  model: z.string(),
  prompt_version: z.string(),
  usage: z.object({ input_tokens: z.number(), output_tokens: z.number() }),
});

export async function parseAgenda(text: string, signal: AbortSignal) {
  const token = await getIdToken();
  if (!token) throw new ApiError(401, "Sign in required");
  const url = process.env.NEXT_PUBLIC_PARSER_URL;
  if (!url)
    throw new ApiError(
      503,
      "Parser is not configured. Enter the agenda manually.",
    );
  let response: Response;
  try {
    const todayParts = new Intl.DateTimeFormat("en-US", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(new Date());
    const part = (type: string) =>
      todayParts.find((item) => item.type === type)?.value ?? "";
    response = await fetch(url, {
      method: "POST",
      signal,
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        text,
        today: `${part("year")}-${part("month")}-${part("day")}`,
        tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
      }),
    });
  } catch (error) {
    if (signal.aborted) throw error;
    throw new ApiError(0, "Network failed. You can enter the agenda manually.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const fallback: Record<number, string> = {
      413: "Text is too long (10,000 characters maximum).",
      422: "The model could not find an agenda. You can enter it manually.",
      429: "Parser is busy. Try again shortly.",
    };
    throw new ApiError(
      response.status,
      fallback[response.status] ?? body.error ?? "Parser unavailable.",
    );
  }
  return parseSchema.parse(await response.json());
}
