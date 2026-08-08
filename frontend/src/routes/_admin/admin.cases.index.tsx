import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Search } from "lucide-react"
import { useState } from "react"
import type { CasePriority, CaseStatus } from "@/client"
import { PriorityBadge, StatusBadge } from "@/components/StatusBadge"
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/StatusPanel"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"

export const Route = createFileRoute("/_admin/admin/cases/")({
  component: CasesPage,
  head: () => ({ meta: [{ title: "Case queue — Tahr Desk" }] }),
})

function CasesPage() {
  const [status, setStatus] = useState<CaseStatus | "">("")
  const [priority, setPriority] = useState<CasePriority | "">("")
  const [search, setSearch] = useState("")
  const query = useQuery({
    queryKey: ["staff-cases", status, priority, search],
    queryFn: () =>
      api.staff.cases({
        query: {
          limit: 100,
          status: status || undefined,
          priority: priority || undefined,
          search: search || undefined,
        },
      }),
  })
  return (
    <div>
      <p className="eyebrow">Case management</p>
      <h1 className="text-4xl font-black">Case queue</h1>
      <div className="surface mt-7 grid gap-3 p-4 md:grid-cols-[1fr_190px_170px]">
        <div className="relative">
          <label className="sr-only" htmlFor="case-search">
            Search cases
          </label>
          <Search
            className="absolute left-3 top-3 size-5 text-ink/70"
            aria-hidden="true"
          />
          <Input
            id="case-search"
            className="pl-10"
            placeholder="Search subject or location"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <select
          aria-label="Filter by status"
          className="min-h-11 rounded-md border bg-card px-3"
          value={status}
          onChange={(event) => setStatus(event.target.value as CaseStatus | "")}
        >
          <option value="">All statuses</option>
          {[
            "submitted",
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
        <select
          aria-label="Filter by priority"
          className="min-h-11 rounded-md border bg-card px-3"
          value={priority}
          onChange={(event) =>
            setPriority(event.target.value as CasePriority | "")
          }
        >
          <option value="">All priorities</option>
          {["low", "normal", "high", "urgent"].map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
      </div>
      {query.isLoading && (
        <div className="mt-5">
          <LoadingPanel label="Loading cases" />
        </div>
      )}
      {query.isError && (
        <div className="mt-5">
          <ErrorPanel retry={() => query.refetch()} />
        </div>
      )}
      {query.data && query.data.count === 0 && (
        <div className="mt-5">
          <EmptyPanel title="No matching cases">
            <p>Adjust the filters or check another queue.</p>
          </EmptyPanel>
        </div>
      )}
      <div className="mt-5 grid gap-3">
        {query.data?.data.map((item) => (
          <Link
            key={item.id}
            to="/admin/cases/$caseId"
            params={{ caseId: item.id }}
            className="surface grid gap-4 p-5 hover:border-mineral/35 md:grid-cols-[1fr_auto] md:items-center"
          >
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <code className="text-xs font-black text-ink/70">
                  {item.reference}
                </code>
                <StatusBadge status={item.status} />
                <PriorityBadge priority={item.priority} />
              </div>
              <h2 className="mt-2 text-lg font-black">{item.subject}</h2>
              <p className="mt-1 text-sm text-ink/70">
                {item.location_text} · {item.category.name}
              </p>
            </div>
            <div className="text-sm md:text-right">
              <p className="font-bold">
                {item.assigned_to?.full_name ?? "Unassigned"}
              </p>
              <p className="text-ink/70">
                Updated {new Date(item.updated_at).toLocaleDateString("en-CA")}
              </p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
