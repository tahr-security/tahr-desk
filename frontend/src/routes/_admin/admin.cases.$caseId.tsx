import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Download } from "lucide-react"
import { useState } from "react"
import type {
  CasePriority,
  CaseStatus,
  ClosureReason,
  TransitionRequest,
  Visibility,
} from "@/client"
import { SafeHtml } from "@/components/SafeHtml"
import { PriorityBadge, StatusBadge } from "@/components/StatusBadge"
import { ErrorPanel, LoadingPanel } from "@/components/StatusPanel"
import { Button } from "@/components/ui/button"
import useAuth from "@/hooks/useAuth"
import { ApiError, api, downloadStaffAttachment } from "@/lib/api"

export const Route = createFileRoute("/_admin/admin/cases/$caseId")({
  component: CaseDetail,
  head: () => ({ meta: [{ title: "Case detail — Tahr Desk" }] }),
})

function CaseDetail() {
  const { caseId } = Route.useParams()
  const client = useQueryClient()
  const { user } = useAuth()
  const [nextStatus, setNextStatus] = useState<CaseStatus>("in_progress")
  const [summary, setSummary] = useState("")
  const [closureReason, setClosureReason] = useState<ClosureReason | "">("")
  const [messageBody, setMessageBody] = useState("")
  const [visibility, setVisibility] = useState<Visibility>("public")
  const [categoryId, setCategoryId] = useState("")
  const [priority, setPriority] = useState<CasePriority | "">("")
  const query = useQuery({
    queryKey: ["staff-case", caseId],
    queryFn: () => api.staff.case(caseId),
  })
  const services = useQuery({ queryKey: ["services"], queryFn: api.services })
  const agents = useQuery({
    queryKey: ["agents"],
    queryFn: api.admin.agents,
    enabled: !!user?.is_superuser,
  })
  const refresh = async () =>
    client.invalidateQueries({ queryKey: ["staff-case", caseId] })
  const claim = useMutation({
    mutationFn: (targetId: string | null) =>
      api.staff.assign(caseId, query.data!.version, {
        assigned_to_id: targetId,
      }),
    onSuccess: refresh,
  })
  const classify = useMutation({
    mutationFn: () =>
      api.staff.classify(caseId, query.data!.version, {
        category_id: categoryId || query.data!.category.id,
        priority: priority || query.data!.priority,
      }),
    onSuccess: refresh,
  })
  const transition = useMutation({
    mutationFn: (body: TransitionRequest) =>
      api.staff.transition(caseId, query.data!.version, body),
    onSuccess: async () => {
      setSummary("")
      await refresh()
    },
  })
  const message = useMutation({
    mutationFn: () =>
      api.staff.message(caseId, query.data!.version, {
        body_markdown: messageBody,
        visibility,
        photos: [],
      }),
    onSuccess: async () => {
      setMessageBody("")
      await refresh()
    },
  })
  const mutationPending =
    claim.isPending ||
    classify.isPending ||
    transition.isPending ||
    message.isPending
  if (query.isLoading) return <LoadingPanel label="Loading case" />
  if (query.isError || !query.data)
    return <ErrorPanel retry={() => query.refetch()} />
  const item = query.data
  const attachments = [
    ...item.attachments,
    ...item.messages.flatMap((entry) => entry.attachments ?? []),
  ]
  const canMutate =
    !!user && (user.is_superuser || item.assigned_to?.id === user.id)
  const stale = [
    claim.error,
    classify.error,
    transition.error,
    message.error,
  ].some((error) => error instanceof ApiError && error.status === 412)
  return (
    <div>
      <Link
        to="/admin/cases"
        className="font-bold text-mineral hover:underline"
      >
        ← Case queue
      </Link>
      {stale && (
        <div
          className="mt-5 rounded-xl border border-amber/40 bg-amber/10 p-4"
          role="alert"
        >
          This case changed in another session.{" "}
          <button
            type="button"
            className="font-bold underline"
            onClick={() => query.refetch()}
          >
            Reload current case
          </button>
          .
        </div>
      )}
      <div className="mt-5 grid gap-6 xl:grid-cols-[1fr_360px]">
        <article className="surface p-6 sm:p-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <code className="text-sm font-black text-ink/70">
                {item.reference}
              </code>
              <h1 className="mt-2 text-3xl font-black">{item.subject}</h1>
              <p className="mt-2 text-ink/70">{item.location_text}</p>
            </div>
            <div className="flex gap-2">
              <StatusBadge status={item.status} />
              <PriorityBadge priority={item.priority} />
            </div>
          </div>
          <dl className="mt-7 grid gap-4 rounded-xl bg-paper p-5 sm:grid-cols-3">
            <div>
              <dt className="text-xs font-black uppercase text-ink/70">
                Resident
              </dt>
              <dd className="mt-1 font-bold">
                {item.reporter_name}
                <br />
                <span className="font-normal">{item.reporter_email}</span>
              </dd>
            </div>
            <div>
              <dt className="text-xs font-black uppercase text-ink/70">
                Service
              </dt>
              <dd className="mt-1 font-bold">{item.category.name}</dd>
            </div>
            <div>
              <dt className="text-xs font-black uppercase text-ink/70">
                Assigned to
              </dt>
              <dd className="mt-1 font-bold">
                {item.assigned_to?.full_name ?? "Unassigned"}
              </dd>
            </div>
          </dl>
          <section className="mt-8">
            <h2 className="text-xl font-black">Resident description</h2>
            <p className="mt-3 whitespace-pre-wrap leading-7 text-ink/75">
              {item.description}
            </p>
          </section>
          {attachments.length > 0 && (
            <section className="mt-8" aria-labelledby="staff-photos-heading">
              <h2 id="staff-photos-heading" className="text-xl font-black">
                Case photos
              </h2>
              <div className="mt-4 flex flex-wrap gap-3">
                {attachments.map((attachment) => (
                  <Button
                    key={attachment.id}
                    variant="outline"
                    onClick={() =>
                      downloadStaffAttachment(
                        attachment.id,
                        attachment.display_name,
                      )
                    }
                  >
                    <Download /> {attachment.display_name}
                  </Button>
                ))}
              </div>
            </section>
          )}
          <section className="mt-8">
            <h2 className="text-xl font-black">Timeline and notes</h2>
            <ol className="mt-5 space-y-4 border-l-2 border-spruce/15 pl-5">
              {item.events.map((event) => (
                <li key={event.id}>
                  <p className="font-bold">{event.summary}</p>
                  <time className="text-sm text-ink/70">
                    {new Date(event.created_at).toLocaleString("en-CA")}
                  </time>
                </li>
              ))}
              {item.messages.map((entry) => (
                <li key={entry.id} className="rounded-lg bg-paper p-4">
                  <p className="text-sm font-black text-mineral">
                    {entry.author_label}
                  </p>
                  <SafeHtml className="mt-1" html={entry.body_html} />
                  <time className="mt-2 block text-xs text-ink/70">
                    {new Date(entry.created_at).toLocaleString("en-CA")}
                  </time>
                </li>
              ))}
            </ol>
          </section>
        </article>
        <aside className="space-y-5">
          <section className="surface p-6">
            <h2 className="text-xl font-black">Ownership</h2>
            {!item.assigned_to && (
              <Button
                className="mt-4 w-full"
                disabled={mutationPending}
                onClick={() => claim.mutate(user!.id)}
              >
                {claim.isPending ? "Claiming…" : "Claim this case"}
              </Button>
            )}
            {item.assigned_to && (
              <p className="mt-3 text-sm text-ink/70">
                Assigned to{" "}
                {item.assigned_to.full_name ?? item.assigned_to.email}.{" "}
                {canMutate
                  ? "You may update this case."
                  : "Only the assignee or a superuser may change it."}
              </p>
            )}
            {user?.is_superuser && agents.data && (
              <>
                <label className="field-label mt-4" htmlFor="assignee">
                  Reassign
                </label>
                <select
                  id="assignee"
                  className="min-h-11 w-full rounded-md border bg-card px-3"
                  disabled={mutationPending}
                  value={item.assigned_to?.id ?? ""}
                  onChange={(event) => claim.mutate(event.target.value || null)}
                >
                  <option value="" disabled={item.status !== "submitted"}>
                    Unassigned
                  </option>
                  {user && (
                    <option value={user.id}>
                      {user.full_name ?? user.email}
                    </option>
                  )}
                  {agents.data.data
                    .filter((agent) => agent.is_active)
                    .map((agent) => (
                      <option key={agent.id} value={agent.id}>
                        {agent.full_name}
                      </option>
                    ))}
                </select>
              </>
            )}
          </section>
          <section className="surface p-6">
            <h2 className="text-xl font-black">Classification</h2>
            <label className="field-label mt-4" htmlFor="case-category">
              Service
            </label>
            <select
              id="case-category"
              className="min-h-11 w-full rounded-md border bg-card px-3"
              value={categoryId || item.category.id}
              onChange={(event) => setCategoryId(event.target.value)}
            >
              {services.data?.data.map((service) => (
                <option key={service.id} value={service.id}>
                  {service.name}
                </option>
              ))}
            </select>
            <label className="field-label mt-4" htmlFor="case-priority">
              Priority
            </label>
            <select
              id="case-priority"
              className="min-h-11 w-full rounded-md border bg-card px-3 capitalize"
              value={priority || item.priority}
              onChange={(event) =>
                setPriority(event.target.value as CasePriority)
              }
            >
              {(["low", "normal", "high", "urgent"] as CasePriority[]).map(
                (value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ),
              )}
            </select>
            <Button
              className="mt-4 w-full"
              disabled={!canMutate || mutationPending}
              onClick={() => classify.mutate()}
            >
              {classify.isPending ? "Saving…" : "Save classification"}
            </Button>
          </section>
          <section className="surface p-6">
            <h2 className="text-xl font-black">Change status</h2>
            <label className="field-label mt-4" htmlFor="next-status">
              New status
            </label>
            <select
              id="next-status"
              className="min-h-11 w-full rounded-md border bg-card px-3"
              value={nextStatus}
              onChange={(event) =>
                setNextStatus(event.target.value as CaseStatus)
              }
            >
              {[
                "triaged",
                "in_progress",
                "waiting_on_reporter",
                "resolved",
                "closed",
              ].map((value) => (
                <option key={value} value={value}>
                  {value.replace(/_/g, " ")}
                </option>
              ))}
            </select>
            <label className="field-label mt-4" htmlFor="transition-summary">
              Public summary
            </label>
            <textarea
              id="transition-summary"
              className="text-area"
              value={summary}
              onChange={(event) => setSummary(event.target.value)}
            />
            {nextStatus === "closed" && (
              <>
                <label className="field-label mt-4" htmlFor="closure">
                  Closure reason
                </label>
                <select
                  id="closure"
                  className="min-h-11 w-full rounded-md border bg-card px-3"
                  value={closureReason}
                  onChange={(event) =>
                    setClosureReason(event.target.value as ClosureReason)
                  }
                >
                  <option value="">Choose reason</option>
                  {["resolved", "out_of_scope", "withdrawn"].map((value) => (
                    <option key={value} value={value}>
                      {value.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </>
            )}
            <Button
              className="mt-4 w-full"
              disabled={
                !canMutate || summary.trim().length < 2 || mutationPending
              }
              onClick={() =>
                transition.mutate({
                  status: nextStatus,
                  summary_markdown: summary,
                  closure_reason: closureReason || null,
                })
              }
            >
              {transition.isPending ? "Updating…" : "Update status"}
            </Button>
          </section>
          <section className="surface p-6">
            <h2 className="text-xl font-black">Add message</h2>
            <label className="field-label mt-4" htmlFor="visibility">
              Visibility
            </label>
            <select
              id="visibility"
              className="min-h-11 w-full rounded-md border bg-card px-3"
              value={visibility}
              onChange={(event) =>
                setVisibility(event.target.value as Visibility)
              }
            >
              <option value="public">Public update</option>
              <option value="private">Private staff note</option>
            </select>
            <label className="field-label mt-4" htmlFor="staff-message">
              Message
            </label>
            <textarea
              id="staff-message"
              className="text-area"
              value={messageBody}
              onChange={(event) => setMessageBody(event.target.value)}
            />
            <Button
              className="mt-4 w-full"
              disabled={
                !canMutate || messageBody.trim().length < 2 || mutationPending
              }
              onClick={() => message.mutate()}
            >
              {message.isPending
                ? "Saving…"
                : visibility === "private"
                  ? "Save private note"
                  : "Post public update"}
            </Button>
          </section>
        </aside>
      </div>
    </div>
  )
}
