import { Link } from "@tanstack/react-router"
import { AlertCircle } from "lucide-react"
import { Brand } from "@/components/Brand"
import { Button } from "@/components/ui/button"

export default function ErrorComponent() {
  return (
    <main
      className="flex min-h-dvh items-center justify-center bg-paper p-5 text-ink"
      data-testid="error-component"
    >
      <div className="surface w-full max-w-xl p-8 text-center sm:p-12">
        <Brand className="mb-9 justify-center" />
        <AlertCircle
          className="mx-auto mb-4 size-14 text-destructive"
          aria-hidden="true"
        />
        <p className="eyebrow">Unexpected error</p>
        <h1 className="text-4xl font-black">Something went wrong.</h1>
        <p className="mt-4 text-ink/70">
          Try the page again or return to the service directory.
        </p>
        <Button asChild size="lg" className="mt-7">
          <Link to="/">Back to services</Link>
        </Button>
      </div>
    </main>
  )
}
