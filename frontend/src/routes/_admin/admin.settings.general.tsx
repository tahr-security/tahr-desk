import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Navigate } from "@tanstack/react-router"
import { useEffect, useState } from "react"
import { ErrorPanel, LoadingPanel } from "@/components/StatusPanel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import useAuth from "@/hooks/useAuth"
import { api } from "@/lib/api"

export const Route = createFileRoute("/_admin/admin/settings/general")({
  component: GeneralSettings,
  head: () => ({ meta: [{ title: "General settings — Tahr Desk" }] }),
})

function GeneralSettings() {
  const { user } = useAuth()
  const client = useQueryClient()
  const query = useQuery({
    queryKey: ["admin-site"],
    queryFn: api.admin.site,
    enabled: !!user?.is_superuser,
  })
  const [organization, setOrganization] = useState("")
  const [area, setArea] = useState("")
  const [timezone, setTimezone] = useState("America/Toronto")
  const [introduction, setIntroduction] = useState("")
  useEffect(() => {
    if (query.data) {
      setOrganization(query.data.organization_name)
      setArea(query.data.service_area)
      setTimezone(query.data.timezone)
      setIntroduction(query.data.introduction_markdown)
    }
  }, [query.data])
  const save = useMutation({
    mutationFn: () =>
      api.admin.updateSite({
        organization_name: organization,
        service_area: area,
        timezone,
        introduction_markdown: introduction,
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["admin-site"] }),
  })
  if (user && !user.is_superuser) return <Navigate to="/admin/forbidden" />
  if (query.isLoading) return <LoadingPanel label="Loading site settings" />
  if (query.isError) return <ErrorPanel retry={() => query.refetch()} />
  return (
    <div className="max-w-3xl">
      <p className="eyebrow">Public content</p>
      <h1 className="text-4xl font-black">General settings</h1>
      <form
        className="surface mt-7 grid gap-5 p-6 sm:p-8"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate()
        }}
      >
        <div>
          <label className="field-label" htmlFor="organization">
            Organization name
          </label>
          <Input
            id="organization"
            value={organization}
            onChange={(event) => setOrganization(event.target.value)}
          />
        </div>
        <div>
          <label className="field-label" htmlFor="service-area">
            Service area
          </label>
          <Input
            id="service-area"
            value={area}
            onChange={(event) => setArea(event.target.value)}
          />
        </div>
        <div>
          <label className="field-label" htmlFor="timezone">
            Display timezone
          </label>
          <Input
            id="timezone"
            value={timezone}
            onChange={(event) => setTimezone(event.target.value)}
          />
        </div>
        <div>
          <label className="field-label" htmlFor="introduction">
            Public introduction (Markdown)
          </label>
          <textarea
            id="introduction"
            className="text-area"
            value={introduction}
            onChange={(event) => setIntroduction(event.target.value)}
          />
        </div>
        {save.isSuccess && (
          <p className="font-bold text-pine" role="status">
            Settings saved.
          </p>
        )}
        {save.isError && (
          <p className="field-error" role="alert">
            Settings could not be saved.
          </p>
        )}
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? "Saving…" : "Save settings"}
        </Button>
      </form>
    </div>
  )
}
