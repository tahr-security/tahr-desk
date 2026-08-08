import { createFileRoute, Link } from "@tanstack/react-router"
import { ShieldX } from "lucide-react"
import { Button } from "@/components/ui/button"

export const Route = createFileRoute("/_admin/admin/forbidden")({
  component: ForbiddenPage,
  head: () => ({ meta: [{ title: "Access denied — Tahr Desk" }] }),
})

function ForbiddenPage() {
  return (
    <section className="surface mx-auto max-w-xl p-9 text-center">
      <ShieldX
        className="mx-auto size-12 text-destructive"
        aria-hidden="true"
      />
      <p className="eyebrow mt-5">403 · Access denied</p>
      <h1 className="text-3xl font-black">
        You do not have access to this area.
      </h1>
      <p className="mt-3 text-ink/70">
        Your account remains signed in. Return to a staff workspace available to
        your role.
      </p>
      <Button asChild className="mt-7">
        <Link to="/admin">Return to dashboard</Link>
      </Button>
    </section>
  )
}
