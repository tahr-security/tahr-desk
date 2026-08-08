import { createFileRoute, redirect } from "@tanstack/react-router"
import { UsersService } from "@/client"
import { AdminShell } from "@/components/AdminShell"
import { isLoggedIn } from "@/hooks/useAuth"

export const Route = createFileRoute("/_admin")({
  component: AdminShell,
  beforeLoad: async () => {
    if (!isLoggedIn()) throw redirect({ to: "/login" })
    try {
      await UsersService.readUserMe()
    } catch {
      sessionStorage.removeItem("access_token")
      throw redirect({ to: "/login" })
    }
  },
})
