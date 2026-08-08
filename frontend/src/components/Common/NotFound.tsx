import { Link } from "@tanstack/react-router"
import { MapPinOff } from "lucide-react"
import { Brand } from "@/components/Brand"
import { Button } from "@/components/ui/button"

export default function NotFound() {
  return (
    <main
      className="flex min-h-dvh items-center justify-center bg-paper p-5 text-ink"
      data-testid="not-found"
    >
      <div className="surface w-full max-w-xl p-8 text-center sm:p-12">
        <Brand className="mb-9 justify-center" />
        <MapPinOff
          className="mx-auto mb-4 size-14 text-mineral"
          aria-hidden="true"
        />
        <p className="eyebrow">404 · Route not found</p>
        <h1 className="text-4xl font-black">That page is not available.</h1>
        <p className="mt-4 text-ink/70">
          Return to Pinehaven Civic Services to find the right service.
        </p>
        <Button asChild size="lg" className="mt-7">
          <Link to="/">Back to services</Link>
        </Button>
      </div>
    </main>
  )
}
