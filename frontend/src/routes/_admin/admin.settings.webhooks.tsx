import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Navigate } from "@tanstack/react-router"
import { Webhook } from "lucide-react"
import { useState } from "react"
import { ErrorPanel, LoadingPanel } from "@/components/StatusPanel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import useAuth from "@/hooks/useAuth"
import { api } from "@/lib/api"

export const Route = createFileRoute("/_admin/admin/settings/webhooks")({
  component: WebhookSettings,
  head: () => ({ meta: [{ title: "Webhooks — Tahr Desk" }] }),
})

function WebhookSettings() {
  const { user } = useAuth()
  const client = useQueryClient()
  const [name, setName] = useState("")
  const [url, setUrl] = useState("")
  const [secret, setSecret] = useState<string | null>(null)
  const site = useQuery({
    queryKey: ["admin-site"],
    queryFn: api.admin.site,
    enabled: !!user?.is_superuser,
  })
  const hooks = useQuery({
    queryKey: ["webhooks"],
    queryFn: api.admin.webhooks,
    enabled: !!user?.is_superuser && site.data?.webhooks_enabled === true,
  })
  const create = useMutation({
    mutationFn: () =>
      api.admin.createWebhook({
        name,
        url,
        subscribed_events: ["case.status_changed", "case.message_added"],
      }),
    onSuccess: (value) => {
      setSecret(value.signing_secret)
      setName("")
      setUrl("")
      client.invalidateQueries({ queryKey: ["webhooks"] })
    },
  })
  if (user && !user.is_superuser) return <Navigate to="/admin/forbidden" />
  if (site.isLoading)
    return <LoadingPanel label="Loading webhook configuration" />
  if (site.isError || !site.data)
    return <ErrorPanel retry={() => site.refetch()} />
  if (!site.data.webhooks_enabled)
    return (
      <section className="surface max-w-2xl p-8">
        <Webhook className="size-10 text-mineral" aria-hidden="true" />
        <p className="eyebrow mt-5">Integration boundary</p>
        <h1 className="text-3xl font-black">Webhook delivery is disabled</h1>
        <p className="mt-3 leading-7 text-ink/70">
          This deployment does not permit outbound webhook delivery. No endpoint
          controls are shown. Set <code>WEBHOOK_DELIVERY_ENABLED=true</code>{" "}
          only in an approved standalone deployment.
        </p>
      </section>
    )
  if (hooks.isLoading) return <LoadingPanel label="Loading webhooks" />
  if (hooks.isError || !hooks.data)
    return <ErrorPanel retry={() => hooks.refetch()} />
  return (
    <div>
      <p className="eyebrow">Integrations</p>
      <h1 className="text-4xl font-black">Webhooks</h1>
      {secret && (
        <div
          className="mt-6 rounded-xl border border-amber/40 bg-amber/10 p-5"
          role="status"
        >
          <h2 className="font-black">Copy this signing secret now</h2>
          <code className="mt-2 block break-all">{secret}</code>
          <p className="mt-2 text-sm">It will not be shown again.</p>
        </div>
      )}
      <form
        className="surface mt-6 grid gap-4 p-6 md:grid-cols-[1fr_2fr_auto] md:items-end"
        onSubmit={(event) => {
          event.preventDefault()
          create.mutate()
        }}
      >
        <div>
          <label className="field-label" htmlFor="webhook-name">
            Name
          </label>
          <Input
            id="webhook-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
        </div>
        <div>
          <label className="field-label" htmlFor="webhook-url">
            HTTPS endpoint
          </label>
          <Input
            id="webhook-url"
            type="url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            required
          />
        </div>
        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? "Creating…" : "Add endpoint"}
        </Button>
      </form>
      <div className="mt-6 grid gap-3">
        {hooks.data.data.map((hook) => (
          <article className="surface p-5" key={hook.id}>
            <div className="flex flex-wrap justify-between gap-3">
              <div>
                <h2 className="font-black">{hook.name}</h2>
                <p className="mt-1 break-all text-sm text-ink/70">{hook.url}</p>
              </div>
              <span className="text-sm font-bold">
                {hook.is_active ? "Active" : "Inactive"}
              </span>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}
