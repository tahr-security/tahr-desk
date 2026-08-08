import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Search } from "lucide-react"
import { useState } from "react"
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/StatusPanel"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"

export const Route = createFileRoute("/_public/services/")({
  component: ServicesPage,
  head: () => ({ meta: [{ title: "Services — Tahr Desk" }] }),
})

function ServicesPage() {
  const [term, setTerm] = useState("")
  const query = useQuery({ queryKey: ["services"], queryFn: api.services })
  if (query.isLoading)
    return (
      <div className="page-container py-16">
        <LoadingPanel label="Loading services" />
      </div>
    )
  if (query.isError || !query.data)
    return (
      <div className="page-container py-16">
        <ErrorPanel retry={() => query.refetch()} />
      </div>
    )
  const shown = query.data.data.filter((item) =>
    `${item.name} ${item.summary}`.toLowerCase().includes(term.toLowerCase()),
  )
  return (
    <div className="page-container py-12 sm:py-16">
      <p className="eyebrow">Pinehaven Civic Services</p>
      <h1 className="text-4xl font-black sm:text-5xl">Service directory</h1>
      <p className="mt-3 max-w-2xl text-lg text-ink/70">
        Choose the closest category. Staff can reclassify your request if
        needed.
      </p>
      <div className="relative mt-8 max-w-xl">
        <Search
          className="absolute left-3 top-3 size-5 text-ink/70"
          aria-hidden="true"
        />
        <Input
          className="h-11 pl-11"
          value={term}
          onChange={(event) => setTerm(event.target.value)}
          placeholder="Search services"
          aria-label="Search services"
        />
      </div>
      <div className="mt-8 grid gap-5 md:grid-cols-2">
        {shown.map((service) => (
          <Link
            key={service.id}
            to="/services/$slug"
            params={{ slug: service.slug }}
            className="surface block p-6"
          >
            <h2 className="text-xl font-black">{service.name}</h2>
            <p className="mt-2 text-ink/70">{service.summary}</p>
            <p className="mt-5 text-sm font-bold text-mineral">
              Response target: {service.response_target_hours} hours
            </p>
          </Link>
        ))}
      </div>
      {shown.length === 0 && (
        <EmptyPanel title="No matching services">
          <p>Try a broader search or browse the complete directory.</p>
        </EmptyPanel>
      )}
    </div>
  )
}
