import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import {
  CircleAlert,
  ClipboardList,
  Clock3,
  UserRoundCheck,
} from "lucide-react"
import { ErrorPanel, LoadingPanel } from "@/components/StatusPanel"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"

export const Route = createFileRoute("/_admin/admin/")({
  component: Dashboard,
  head: () => ({ meta: [{ title: "Staff dashboard — Tahr Desk" }] }),
})

function Dashboard() {
  const query = useQuery({
    queryKey: ["staff-dashboard"],
    queryFn: api.staff.dashboard,
  })
  if (query.isLoading) return <LoadingPanel label="Loading service desk" />
  if (query.isError || !query.data)
    return <ErrorPanel retry={() => query.refetch()} />
  const cards = [
    [UserRoundCheck, "Assigned to me", query.data.mine],
    [ClipboardList, "Unassigned", query.data.unassigned],
    [CircleAlert, "Overdue", query.data.overdue],
    [Clock3, "Open total", query.data.open_total],
  ]
  return (
    <div>
      <p className="eyebrow">Staff workspace</p>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl font-black">Service desk overview</h1>
          <p className="mt-2 text-ink/70">
            Prioritize the queue and keep residents informed.
          </p>
        </div>
        <Button asChild>
          <Link to="/admin/cases">Open case queue</Link>
        </Button>
      </div>
      <section
        className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
        aria-label="Case statistics"
      >
        {cards.map(([Icon, label, value]) => {
          const StatIcon = Icon as typeof ClipboardList
          return (
            <article className="surface p-5" key={String(label)}>
              <StatIcon
                className="mb-7 size-7 text-mineral"
                aria-hidden="true"
              />
              <p className="text-3xl font-black">{String(value)}</p>
              <p className="mt-1 text-sm font-bold text-ink/70">
                {String(label)}
              </p>
            </article>
          )
        })}
      </section>
      <section className="surface mt-6 p-6">
        <p className="text-sm font-bold text-mineral">Last seven days</p>
        <h2 className="mt-1 text-2xl font-black">
          {query.data.resolved_last_7_days} requests resolved
        </h2>
        <p className="mt-2 text-ink/70">
          Resolution totals include cases awaiting final closure.
        </p>
      </section>
    </div>
  )
}
