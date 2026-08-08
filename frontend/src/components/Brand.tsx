import { Link } from "@tanstack/react-router"
import { Mountain } from "lucide-react"
import { cn } from "@/lib/utils"

export function Brand({ className }: { className?: string }) {
  return (
    <Link
      to="/"
      className={cn(
        "inline-flex items-center gap-2 rounded-lg text-spruce focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-mineral/50",
        className,
      )}
      aria-label="Tahr Desk home"
    >
      <span className="grid size-10 place-items-center rounded-xl bg-spruce text-white">
        <Mountain className="size-6" aria-hidden="true" />
      </span>
      <span className="text-xl font-extrabold tracking-tight">Tahr Desk</span>
    </Link>
  )
}
