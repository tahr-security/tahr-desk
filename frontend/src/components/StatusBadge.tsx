import type { CasePriority, CaseStatus } from "@/client"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

const statusLabels: Record<CaseStatus, string> = {
  submitted: "Submitted",
  triaged: "Triaged",
  in_progress: "In progress",
  waiting_on_reporter: "Waiting on resident",
  resolved: "Resolved",
  closed: "Closed",
}

export function StatusBadge({ status }: { status: CaseStatus }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "whitespace-nowrap font-bold",
        status === "submitted" &&
          "border-mineral/30 bg-mineral/10 text-mineral",
        status === "in_progress" &&
          "border-amber/40 bg-amber/15 text-amber-950",
        status === "waiting_on_reporter" &&
          "border-orange-300 bg-orange-50 text-orange-800",
        status === "resolved" && "border-green-300 bg-green-50 text-green-800",
        status === "closed" && "border-slate-300 bg-slate-100 text-slate-700",
      )}
    >
      {statusLabels[status]}
    </Badge>
  )
}

export function PriorityBadge({ priority }: { priority: CasePriority }) {
  return (
    <Badge
      variant="secondary"
      className={cn(
        "capitalize",
        priority === "urgent" && "bg-red-100 text-red-800",
        priority === "high" && "bg-amber-100 text-amber-900",
      )}
    >
      {priority}
    </Badge>
  )
}
