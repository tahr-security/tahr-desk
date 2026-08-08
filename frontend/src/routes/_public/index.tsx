import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import {
  ArrowRight,
  ClipboardCheck,
  MapPinned,
  MessageSquareText,
} from "lucide-react"
import { ErrorPanel, LoadingPanel } from "@/components/StatusPanel"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"

export const Route = createFileRoute("/_public/")({
  component: HomePage,
  head: () => ({ meta: [{ title: "Pinehaven Civic Services — Tahr Desk" }] }),
})

function HomePage() {
  const site = useQuery({ queryKey: ["site"], queryFn: api.site })
  const services = useQuery({ queryKey: ["services"], queryFn: api.services })
  if (site.isLoading || services.isLoading)
    return (
      <div className="page-container py-16">
        <LoadingPanel label="Loading civic services" />
      </div>
    )
  if (site.isError || services.isError || !site.data || !services.data)
    return (
      <div className="page-container py-16">
        <ErrorPanel
          retry={() => {
            site.refetch()
            services.refetch()
          }}
        />
      </div>
    )
  return (
    <>
      <section className="overflow-hidden bg-spruce text-white">
        <div className="page-container grid gap-10 py-16 lg:grid-cols-[1.05fr_.95fr] lg:items-end lg:py-24">
          <div>
            <p className="eyebrow !text-amber">{site.data.service_area}</p>
            <h1 className="max-w-3xl text-5xl font-black leading-[1.03] tracking-tight sm:text-6xl">
              Tell us what needs attention.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-white/78">
              Report an issue, keep your private reference, and follow the work
              from intake to resolution.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button
                asChild
                size="lg"
                className="bg-amber text-ink hover:bg-amber/90"
              >
                <Link to="/report">
                  Report an issue <ArrowRight />
                </Link>
              </Button>
              <Button
                asChild
                size="lg"
                variant="outline"
                className="border-white/35 bg-transparent text-white hover:bg-white/10"
              >
                <Link to="/track">Track a request</Link>
              </Button>
            </div>
          </div>
          <ol className="grid grid-cols-3 gap-3" aria-label="How it works">
            {[
              [MapPinned, "1", "Describe the location"],
              [ClipboardCheck, "2", "Receive a reference"],
              [MessageSquareText, "3", "Follow the timeline"],
            ].map(([Icon, n, copy]) => {
              const TileIcon = Icon as typeof MapPinned
              return (
                <li
                  className="rounded-xl border border-white/15 bg-white/8 p-4"
                  key={String(n)}
                >
                  <TileIcon className="mb-8 text-amber" aria-hidden="true" />
                  <p className="text-xs font-black text-white/75">
                    STEP {String(n)}
                  </p>
                  <p className="mt-1 font-bold">{String(copy)}</p>
                </li>
              )
            })}
          </ol>
        </div>
      </section>
      <section
        className="page-container py-16"
        aria-labelledby="services-heading"
      >
        <p className="eyebrow">Available services</p>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 id="services-heading" className="text-4xl font-black">
              Start in the right place
            </h2>
            <p className="mt-2 text-ink/70">
              Response targets begin when your request is submitted.
            </p>
          </div>
          <Button asChild variant="outline">
            <Link to="/services">View all services</Link>
          </Button>
        </div>
        <div className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {services.data.data.map((service) => (
            <Link
              key={service.id}
              to="/services/$slug"
              params={{ slug: service.slug }}
              className="surface group block p-6 transition-transform hover:-translate-y-0.5"
            >
              <p className="text-xs font-black uppercase tracking-wider text-mineral">
                Target: {service.response_target_hours} hours
              </p>
              <h3 className="mt-3 text-xl font-black group-hover:text-mineral">
                {service.name}
              </h3>
              <p className="mt-2 leading-7 text-ink/70">{service.summary}</p>
            </Link>
          ))}
        </div>
      </section>
    </>
  )
}
