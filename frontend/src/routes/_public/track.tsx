import { useMutation } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Clock3, Download, MessageSquarePlus, ShieldCheck } from "lucide-react"
import { useState } from "react"
import type { CaseCredentials, CasePublic } from "@/client"
import { SafeHtml } from "@/components/SafeHtml"
import { StatusBadge } from "@/components/StatusBadge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api, downloadPublicAttachment } from "@/lib/api"

export const Route = createFileRoute("/_public/track")({
  component: TrackPage,
  head: () => ({ meta: [{ title: "Track a request — Tahr Desk" }] }),
})

function TrackPage() {
  const [credentials, setCredentials] = useState<CaseCredentials>({
    reference: "",
    reporter_email: "",
  })
  const [current, setCurrent] = useState<CasePublic | null>(null)
  const [body, setBody] = useState("")
  const lookup = useMutation({
    mutationFn: api.lookupCase,
    onSuccess: setCurrent,
  })
  const message = useMutation({
    mutationFn: () =>
      api.createPublicMessage({
        ...credentials,
        body_markdown: body,
        photos: [],
      }),
    onSuccess: async () => {
      setCurrent(await api.lookupCase(credentials))
      setBody("")
    },
  })
  if (current) {
    const attachments = [
      ...current.attachments,
      ...current.messages.flatMap((entry) => entry.attachments ?? []),
    ]
    return (
      <div className="page-container py-12 sm:py-16">
        <button
          type="button"
          className="font-bold text-mineral hover:underline"
          onClick={() => {
            setCurrent(null)
            lookup.reset()
          }}
        >
          ← Track another request
        </button>
        <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_340px]">
          <article className="surface p-6 sm:p-8">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <code className="font-black tracking-wide">
                  {current.reference}
                </code>
                <h1 className="mt-2 text-3xl font-black">{current.subject}</h1>
                <p className="mt-2 text-ink/70">
                  {current.location_text} · {current.category.name}
                </p>
              </div>
              <StatusBadge status={current.status} />
            </div>
            <section className="mt-9" aria-labelledby="timeline-heading">
              <h2 id="timeline-heading" className="text-xl font-black">
                Public timeline
              </h2>
              <ol className="mt-5 space-y-4 border-l-2 border-spruce/15 pl-5">
                {current.events.map((event) => (
                  <li key={event.id}>
                    <p className="font-bold">{event.summary}</p>
                    <time className="text-sm text-ink/70">
                      {new Date(event.created_at).toLocaleString("en-CA")}
                    </time>
                  </li>
                ))}
                {current.messages.map((item) => (
                  <li key={item.id}>
                    <p className="text-sm font-bold text-mineral">
                      {item.author_label}
                    </p>
                    <SafeHtml html={item.body_html} />
                    <time className="text-sm text-ink/70">
                      {new Date(item.created_at).toLocaleString("en-CA")}
                    </time>
                  </li>
                ))}
              </ol>
            </section>
            {attachments.length > 0 && (
              <section className="mt-9" aria-labelledby="photos-heading">
                <h2 id="photos-heading" className="text-xl font-black">
                  Case photos
                </h2>
                <div className="mt-4 flex flex-wrap gap-3">
                  {attachments.map((attachment) => (
                    <Button
                      key={attachment.id}
                      variant="outline"
                      onClick={() =>
                        downloadPublicAttachment(
                          credentials,
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
          </article>
          <aside className="surface h-fit p-6">
            <MessageSquarePlus className="text-amber" aria-hidden="true" />
            <h2 className="mt-3 text-xl font-black">Add information</h2>
            <p className="mt-2 text-sm text-ink/70">
              Your message becomes part of the public case timeline.
            </p>
            <label className="field-label mt-5" htmlFor="follow-up">
              Message
            </label>
            <textarea
              id="follow-up"
              className="text-area"
              value={body}
              onChange={(event) => setBody(event.target.value)}
            />
            <Button
              className="mt-4 w-full"
              disabled={body.trim().length < 2 || message.isPending}
              onClick={() => message.mutate()}
            >
              {message.isPending ? "Sending…" : "Send follow-up"}
            </Button>
            {message.isError && (
              <p className="field-error" role="alert">
                The message could not be added. Reload the case and try again.
              </p>
            )}
          </aside>
        </div>
      </div>
    )
  }
  return (
    <div className="page-container py-12 sm:py-16">
      <div className="mx-auto max-w-xl">
        <p className="eyebrow">Private case access</p>
        <h1 className="text-4xl font-black sm:text-5xl">Track a request</h1>
        <p className="mt-3 text-lg text-ink/70">
          Enter the reference from your receipt and the same email used to
          report the issue.
        </p>
        <form
          className="surface mt-8 grid gap-5 p-6 sm:p-8"
          onSubmit={(event) => {
            event.preventDefault()
            lookup.mutate(credentials)
          }}
        >
          <ShieldCheck className="size-9 text-mineral" aria-hidden="true" />
          <div>
            <label className="field-label" htmlFor="reference">
              Case reference
            </label>
            <Input
              id="reference"
              autoComplete="off"
              spellCheck={false}
              className="font-mono uppercase"
              value={credentials.reference}
              onChange={(event) =>
                setCredentials({
                  ...credentials,
                  reference: event.target.value.toUpperCase(),
                })
              }
              required
            />
          </div>
          <div>
            <label className="field-label" htmlFor="tracking-email">
              Email address
            </label>
            <Input
              id="tracking-email"
              type="email"
              autoComplete="email"
              value={credentials.reporter_email}
              onChange={(event) =>
                setCredentials({
                  ...credentials,
                  reporter_email: event.target.value,
                })
              }
              required
            />
          </div>
          {lookup.isError && (
            <div
              role="alert"
              className="rounded-lg border border-destructive/30 bg-destructive/5 p-4"
            >
              No request matched those details. Check both fields and try again.
            </div>
          )}
          <Button type="submit" size="lg" disabled={lookup.isPending}>
            {lookup.isPending ? "Looking up…" : "View request"}
          </Button>
          <p className="flex gap-2 text-sm text-ink/70">
            <Clock3 className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            References and email addresses stay out of browser history and page
            URLs.
          </p>
        </form>
      </div>
    </div>
  )
}
