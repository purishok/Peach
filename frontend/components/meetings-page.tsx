"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, parseAgenda, type Agenda, type Meeting } from "@/lib/api";

const emptyAgenda = (): Agenda => ({
  title: null, starts_at: null, duration_minutes: null,
  items: [{ topic: "", owner: null, minutes: null }],
  action_items: [], language: "en",
});

function isoLocal(value: string) {
  return new Date(value).toISOString();
}

export function MeetingsPage() {
  const queryClient = useQueryClient();
  const {data, isPending, error} = useQuery({queryKey: ["meetings"], queryFn: api.listMeetings});
  const [selected, setSelected] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [newStart, setNewStart] = useState("");
  const [newEnd, setNewEnd] = useState("");
  const [creating, setCreating] = useState(false);
  const [text, setText] = useState("");
  const [draft, setAgenda] = useState<Agenda | null>(null);
  const [suggestion, setSuggestion] = useState<{
    agenda: Agenda; model: string; prompt_version: string;
  } | null>(null);
  const [touched, setTouched] = useState<Set<string>>(new Set());
  const [parsing, setParsing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [parseError, setParseError] = useState("");
  const controller = useRef<AbortController | null>(null);
  const meetings = data?.meetings ?? [];
  const meeting = meetings.find((row) => row.id === selected) ?? meetings[0];
  const agenda = draft ?? meeting?.agenda ?? emptyAgenda();

  function choose(row: Meeting) {
    controller.current?.abort();
    setSelected(row.id);
    setAgenda(row.agenda ?? emptyAgenda());
    setSuggestion(null);
    setTouched(new Set());
    setParseError("");
  }

  function edit(path: string, next: Agenda) {
    setAgenda(next);
    setTouched((old) => new Set(old).add(path));
  }

  function badge(path: string, value: unknown) {
    return suggestion && value !== null && value !== "" && !touched.has(path)
      ? <Badge variant="secondary" className="ml-2">suggested</Badge> : null;
  }

  async function create() {
    if (!newTitle.trim() || !newStart || !newEnd) {
      toast.error("Add a title, start and end time"); return;
    }
    setCreating(true);
    try {
      const row = await api.createMeeting({
        title: newTitle.trim(), starts_at: isoLocal(newStart), ends_at: isoLocal(newEnd),
      });
      await queryClient.invalidateQueries({queryKey: ["meetings"]});
      choose(row);
      setNewTitle("");
      toast.success("Meeting created");
    } catch (error) { toast.error((error as Error).message); }
    finally { setCreating(false); }
  }

  async function parse() {
    if (!text.trim()) { setParseError("Paste agenda text first."); return; }
    if (text.length > 10_000) { setParseError("Text is too long (10,000 characters maximum)."); return; }
    const nextController = new AbortController();
    controller.current = nextController;
    setParsing(true); setParseError("");
    try {
      const result = await parseAgenda(text, nextController.signal);
      setAgenda(result.agenda);
      setSuggestion({
        agenda: result.agenda, model: result.model, prompt_version: result.prompt_version,
      });
      setTouched(new Set());
    } catch (error) {
      if (!nextController.signal.aborted) setParseError((error as Error).message);
    } finally {
      if (controller.current === nextController) { controller.current = null; setParsing(false); }
    }
  }

  async function save() {
    if (!meeting) return;
    if (!agenda.items.some((item) => item.topic.trim())) {
      toast.error("Add at least one agenda topic"); return;
    }
    setSaving(true);
    try {
      const finalAgenda = {
        ...agenda,
        items: agenda.items.filter((item) => item.topic.trim()),
        action_items: agenda.action_items.filter((item) => item.task.trim()),
      };
      const row = await api.saveAgenda(meeting.id, finalAgenda, suggestion);
      queryClient.setQueryData<{meetings: Meeting[]}>(["meetings"], (old) => old && ({
        meetings: old.meetings.map((item) => item.id === row.id ? row : item),
      }));
      setSuggestion(null);
      toast.success("Agenda saved");
    } catch (error) { toast.error((error as Error).message); }
    finally { setSaving(false); }
  }

  return <div className="grid gap-8">
    <PageHeader icon="🗓️" title="Meetings" description="Paste an agenda, check every suggestion, then save it." />
    <section className="rounded-xl border p-5 space-y-3">
      <h2 className="text-lg font-semibold">New meeting</h2>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-sm">Title<Input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="Pricing sync" /></label>
        <label className="text-sm">Starts<Input type="datetime-local" value={newStart} onChange={(e) => setNewStart(e.target.value)} /></label>
        <label className="text-sm">Ends<Input type="datetime-local" value={newEnd} onChange={(e) => setNewEnd(e.target.value)} /></label>
      </div>
      <Button onClick={create} disabled={creating}>Create meeting</Button>
    </section>
    {error && <p role="alert">Could not load meetings: {(error as Error).message}</p>}
    {isPending && <p>Loading meetings…</p>}
    {meetings.length > 0 && <div className="grid gap-5 md:grid-cols-[220px_1fr]">
      <nav aria-label="Meetings" className="space-y-1">
        {meetings.map((row) => <button key={row.id} type="button" onClick={() => choose(row)}
          className={`w-full rounded-lg p-3 text-left text-sm ${meeting?.id === row.id ? "bg-accent font-semibold" : "hover:bg-muted"}`}>
          {row.title}<span className="block text-xs text-muted-foreground">{new Date(row.starts_at).toLocaleString()}</span>
        </button>)}
      </nav>
      <div className="space-y-6">
        <div><h2 className="text-xl font-semibold">{meeting?.title}</h2><p className="text-sm text-muted-foreground">{meeting && new Date(meeting.starts_at).toLocaleString()}</p></div>
        <section className="rounded-xl border p-5 space-y-3">
          <h3 className="font-semibold">Paste an agenda</h3>
          <Textarea aria-label="Pasted agenda" value={text} onChange={(e) => setText(e.target.value)} rows={5} placeholder="Пн 10:00, синк по прайсингу…" />
          <p className="text-xs text-muted-foreground">{text.length}/10,000 characters</p>
          {parseError && <p role="alert" className="text-sm text-destructive">{parseError}</p>}
          {parsing && <p role="status" className="text-sm">Reading the agenda… This can take a few seconds.</p>}
          <div className="flex gap-2"><Button onClick={parse} disabled={parsing}>Parse</Button>
            {parsing && <Button variant="outline" onClick={() => {controller.current?.abort(); setParsing(false);}}>Cancel</Button>}</div>
        </section>
        <section className="rounded-xl border p-5 space-y-4">
          <div><h3 className="font-semibold">Check and save</h3><p className="text-sm text-muted-foreground">Edit any field before saving. The model cannot save for you.</p></div>
          <label className="block text-sm">Agenda title{badge("title", agenda.title)}
            <Input value={agenda.title ?? ""} onChange={(e) => edit("title", {...agenda, title: e.target.value || null})} /></label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm">Starts at (ISO 8601 with offset){badge("starts_at", agenda.starts_at)}
              <Input value={agenda.starts_at ?? ""} onChange={(e) => edit("starts_at", {...agenda, starts_at: e.target.value || null})} placeholder="2026-10-26T10:00:00+02:00" /></label>
            <label className="text-sm">Duration (minutes){badge("duration_minutes", agenda.duration_minutes)}
              <Input type="number" min="1" max="600" value={agenda.duration_minutes ?? ""} onChange={(e) => edit("duration_minutes", {...agenda, duration_minutes: e.target.value ? Number(e.target.value) : null})} /></label>
          </div>
          <label className="block max-w-32 text-sm">Language{badge("language", agenda.language)}
            <Input maxLength={2} value={agenda.language} onChange={(e) => edit("language", {...agenda, language: e.target.value.toLowerCase()})} /></label>
          <h4 className="font-medium">Topics</h4>
          {agenda.items.map((item, index) => <div key={index} className="grid gap-2 rounded-lg bg-muted/50 p-3 sm:grid-cols-[1fr_160px_90px]">
            <label className="text-sm">Topic{badge(`items.${index}.topic`, item.topic)}<Input value={item.topic} onChange={(e) => edit(`items.${index}.topic`, {...agenda, items: agenda.items.map((x, i) => i === index ? {...x, topic: e.target.value} : x)})} /></label>
            <label className="text-sm">Owner{badge(`items.${index}.owner`, item.owner)}<Input value={item.owner ?? ""} onChange={(e) => edit(`items.${index}.owner`, {...agenda, items: agenda.items.map((x, i) => i === index ? {...x, owner: e.target.value || null} : x)})} /></label>
            <label className="text-sm">Minutes{badge(`items.${index}.minutes`, item.minutes)}<Input type="number" min="1" max="480" value={item.minutes ?? ""} onChange={(e) => edit(`items.${index}.minutes`, {...agenda, items: agenda.items.map((x, i) => i === index ? {...x, minutes: e.target.value ? Number(e.target.value) : null} : x)})} /></label>
          </div>)}
          <Button variant="outline" onClick={() => setAgenda({...agenda, items: [...agenda.items, {topic: "", owner: null, minutes: null}]})}>Add topic</Button>
          <h4 className="font-medium">Action items</h4>
          {agenda.action_items.map((item, index) => <div key={index} className="grid gap-2 rounded-lg bg-muted/50 p-3 sm:grid-cols-[1fr_160px_140px]">
            <label className="text-sm">Task{badge(`actions.${index}.task`, item.task)}<Input value={item.task} onChange={(e) => edit(`actions.${index}.task`, {...agenda, action_items: agenda.action_items.map((x, i) => i === index ? {...x, task: e.target.value} : x)})} /></label>
            <label className="text-sm">Owner{badge(`actions.${index}.owner`, item.owner)}<Input value={item.owner ?? ""} onChange={(e) => edit(`actions.${index}.owner`, {...agenda, action_items: agenda.action_items.map((x, i) => i === index ? {...x, owner: e.target.value || null} : x)})} /></label>
            <label className="text-sm">Due{badge(`actions.${index}.due`, item.due)}<Input type="date" value={item.due ?? ""} onChange={(e) => edit(`actions.${index}.due`, {...agenda, action_items: agenda.action_items.map((x, i) => i === index ? {...x, due: e.target.value || null} : x)})} /></label>
          </div>)}
          <Button variant="outline" onClick={() => setAgenda({...agenda, action_items: [...agenda.action_items, {task: "", owner: null, due: null}]})}>Add action</Button>
          <div><Button onClick={save} disabled={saving}>{saving ? "Saving…" : "Save agenda"}</Button></div>
        </section>
      </div>
    </div>}
  </div>;
}
