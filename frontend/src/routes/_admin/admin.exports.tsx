import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Download, FileSpreadsheet } from "lucide-react"
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/StatusPanel"
import { Button } from "@/components/ui/button"
import { api, downloadExport } from "@/lib/api"

export const Route = createFileRoute("/_admin/admin/exports")({
  component: ExportsPage,
  head: () => ({ meta: [{ title: "Exports — Tahr Desk" }] }),
})

function ExportsPage() {
  const client = useQueryClient()
  const query = useQuery({
    queryKey: ["exports"],
    queryFn: api.staff.exports,
    refetchInterval: 5000,
  })
  const create = useMutation({
    mutationFn: () =>
      api.staff.createExport({
        kind: "cases_csv",
        idempotency_key: crypto.randomUUID(),
        filters: {},
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["exports"] }),
  })
  return (
    <div>
      <p className="eyebrow">Reports</p>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl font-black">Exports</h1>
          <p className="mt-2 text-ink/70">
            Generated files expire after 24 hours.
          </p>
        </div>
        <Button onClick={() => create.mutate()} disabled={create.isPending}>
          <FileSpreadsheet />
          {create.isPending ? "Queuing…" : "Create CSV export"}
        </Button>
      </div>
      {query.isLoading && (
        <div className="mt-7">
          <LoadingPanel label="Loading exports" />
        </div>
      )}
      {query.isError && (
        <div className="mt-7">
          <ErrorPanel retry={() => query.refetch()} />
        </div>
      )}
      {query.data?.count === 0 && (
        <div className="mt-7">
          <EmptyPanel title="No exports yet">
            <p>Create a filtered CSV from the current service desk data.</p>
          </EmptyPanel>
        </div>
      )}
      <div className="mt-7 grid gap-3">
        {query.data?.data.map((item) => (
          <article
            className="surface flex flex-wrap items-center justify-between gap-4 p-5"
            key={item.id}
          >
            <div>
              <p className="font-black">
                {item.kind === "cases_csv" ? "Case list CSV" : "Case PDF"}
              </p>
              <p className="mt-1 text-sm text-ink/70">
                Created {new Date(item.created_at).toLocaleString("en-CA")} ·{" "}
                <span className="capitalize">{item.status}</span>
              </p>
              {item.error_code && (
                <p className="field-error">
                  Generation failed: {item.error_code}
                </p>
              )}
            </div>
            {item.status === "ready" &&
              item.expires_at &&
              new Date(item.expires_at) > new Date() && (
                <Button
                  variant="outline"
                  onClick={() =>
                    downloadExport(
                      item.id,
                      item.kind === "case_pdf"
                        ? "tahr-desk-case.pdf"
                        : "tahr-desk-cases.csv",
                    )
                  }
                >
                  <Download />
                  Download
                </Button>
              )}
            {(item.status === "expired" ||
              (item.expires_at && new Date(item.expires_at) <= new Date())) && (
              <span className="text-sm font-bold text-ink/70">Expired</span>
            )}
          </article>
        ))}
      </div>
    </div>
  )
}
