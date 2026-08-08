import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Navigate } from "@tanstack/react-router"
import { useState } from "react"
import { ErrorPanel, LoadingPanel } from "@/components/StatusPanel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import useAuth from "@/hooks/useAuth"
import { api } from "@/lib/api"

export const Route = createFileRoute("/_admin/admin/settings/services")({
  component: ServicesSettings,
  head: () => ({ meta: [{ title: "Service setup — Tahr Desk" }] }),
})

function ServicesSettings() {
  const { user } = useAuth()
  const client = useQueryClient()
  const [draft, setDraft] = useState({
    slug: "",
    name: "",
    summary: "",
    guidance_markdown: "",
    response_target_hours: 72,
  })
  const query = useQuery({
    queryKey: ["admin-services"],
    queryFn: api.admin.services,
    enabled: !!user?.is_superuser,
  })
  const refresh = () =>
    client.invalidateQueries({ queryKey: ["admin-services"] })
  const create = useMutation({
    mutationFn: () => api.admin.createService(draft),
    onSuccess: () => {
      setDraft({
        slug: "",
        name: "",
        summary: "",
        guidance_markdown: "",
        response_target_hours: 72,
      })
      refresh()
    },
  })
  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      api.admin.updateService(id, { is_active: active }),
    onSuccess: refresh,
  })
  if (user && !user.is_superuser) return <Navigate to="/admin/forbidden" />
  if (query.isLoading)
    return <LoadingPanel label="Loading service categories" />
  if (query.isError || !query.data)
    return <ErrorPanel retry={() => query.refetch()} />
  return (
    <div>
      <p className="eyebrow">Public service directory</p>
      <h1 className="text-4xl font-black">Service setup</h1>
      <form
        className="surface mt-7 grid gap-4 p-6 lg:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault()
          create.mutate()
        }}
      >
        <h2 className="text-xl font-black lg:col-span-2">Add a service</h2>
        <Field label="Name" htmlFor="new-service-name">
          <Input
            id="new-service-name"
            value={draft.name}
            onChange={(event) =>
              setDraft({ ...draft, name: event.target.value })
            }
            required
          />
        </Field>
        <Field label="Immutable slug" htmlFor="new-service-slug">
          <Input
            id="new-service-slug"
            value={draft.slug}
            pattern="[a-z0-9-]+"
            onChange={(event) =>
              setDraft({ ...draft, slug: event.target.value.toLowerCase() })
            }
            required
          />
        </Field>
        <Field label="Summary" htmlFor="new-service-summary">
          <Input
            id="new-service-summary"
            value={draft.summary}
            onChange={(event) =>
              setDraft({ ...draft, summary: event.target.value })
            }
            required
          />
        </Field>
        <Field label="Response target (hours)" htmlFor="new-service-target">
          <Input
            id="new-service-target"
            type="number"
            min={1}
            value={draft.response_target_hours}
            onChange={(event) =>
              setDraft({
                ...draft,
                response_target_hours: Number(event.target.value),
              })
            }
          />
        </Field>
        <div className="lg:col-span-2">
          <label className="field-label" htmlFor="service-guidance">
            Guidance (Markdown)
          </label>
          <textarea
            id="service-guidance"
            className="text-area"
            value={draft.guidance_markdown}
            onChange={(event) =>
              setDraft({ ...draft, guidance_markdown: event.target.value })
            }
            required
          />
        </div>
        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? "Adding…" : "Add service"}
        </Button>
      </form>
      <div className="mt-6 grid gap-4">
        {query.data.data.map((service) => (
          <article
            className="surface flex flex-wrap items-center justify-between gap-4 p-5"
            key={service.id}
          >
            <div>
              <div className="flex gap-2">
                <h2 className="font-black">{service.name}</h2>
                <span className="text-sm text-ink/70">/{service.slug}</span>
              </div>
              <p className="mt-1 text-sm text-ink/70">
                {service.summary} · {service.response_target_hours}h target
              </p>
            </div>
            <Button
              variant={service.is_active ? "destructive" : "default"}
              onClick={() =>
                toggle.mutate({ id: service.id, active: !service.is_active })
              }
            >
              {service.is_active ? "Deactivate" : "Activate"}
            </Button>
          </article>
        ))}
      </div>
    </div>
  )
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string
  htmlFor: string
  children: React.ReactNode
}) {
  return (
    <div>
      <label className="field-label" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
    </div>
  )
}
