import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Clock } from "lucide-react"
import { SafeHtml } from "@/components/SafeHtml"
import { ErrorPanel, LoadingPanel } from "@/components/StatusPanel"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"

export const Route = createFileRoute("/_public/services/$slug")({
  component: ServicePage,
})

function ServicePage() {
  const { slug } = Route.useParams()
  const query = useQuery({
    queryKey: ["service", slug],
    queryFn: () => api.service(slug),
  })
  if (query.isLoading)
    return (
      <div className="page-container py-16">
        <LoadingPanel label="Loading service guidance" />
      </div>
    )
  if (query.isError || !query.data)
    return (
      <div className="page-container py-16">
        <ErrorPanel retry={() => query.refetch()} />
      </div>
    )
  return (
    <div className="page-container py-12 sm:py-16">
      <Link to="/services" className="font-bold text-mineral hover:underline">
        ← All services
      </Link>
      <div className="mt-6 grid gap-8 lg:grid-cols-[1fr_320px]">
        <article className="surface p-6 sm:p-9">
          <p className="eyebrow">Service guidance</p>
          <h1 className="text-4xl font-black">{query.data.name}</h1>
          <p className="mt-4 text-lg text-ink/70">{query.data.summary}</p>
          <SafeHtml className="mt-8" html={query.data.guidance_html} />
        </article>
        <aside className="surface h-fit p-6">
          <Clock className="mb-4 text-amber" aria-hidden="true" />
          <h2 className="text-xl font-black">Response standard</h2>
          <p className="mt-2 text-ink/70">
            We aim to review requests within {query.data.response_target_hours}{" "}
            hours.
          </p>
          <Button asChild className="mt-6 w-full">
            <Link to="/report">Report this issue</Link>
          </Button>
        </aside>
      </div>
    </div>
  )
}
