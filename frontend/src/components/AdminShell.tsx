import { Link, Outlet } from "@tanstack/react-router"
import {
  ClipboardList,
  Download,
  LayoutDashboard,
  LogOut,
  Settings,
  UserCog,
} from "lucide-react"
import { Brand } from "@/components/Brand"
import { Button } from "@/components/ui/button"
import useAuth from "@/hooks/useAuth"

const linkClass =
  "flex min-h-11 shrink-0 items-center gap-2 rounded-lg px-3 font-bold text-ink/70 transition-colors hover:bg-pine/8 hover:text-ink focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-mineral/50 [&.active]:bg-spruce [&.active]:text-white"

export function AdminShell() {
  const { logout, user } = useAuth()
  return (
    <div className="min-h-dvh bg-paper text-ink">
      <a className="skip-link" href="#admin-content">
        Skip to content
      </a>
      <header className="border-b border-spruce/10 bg-card">
        <div className="page-container flex min-h-18 flex-wrap items-center justify-between gap-3 py-2">
          <Brand />
          <div className="flex items-center gap-3 text-sm">
            <span className="hidden text-ink/70 sm:inline">{user?.email}</span>
            <Button variant="outline" className="min-h-11" onClick={logout}>
              <LogOut aria-hidden="true" /> Log out
            </Button>
          </div>
        </div>
      </header>
      <div className="page-container grid gap-6 py-6 lg:grid-cols-[230px_1fr]">
        <nav
          aria-label="Staff navigation"
          className="flex gap-2 overflow-x-auto lg:flex-col"
        >
          <Link
            to="/admin"
            className={linkClass}
            activeOptions={{ exact: true }}
          >
            <LayoutDashboard aria-hidden="true" /> Overview
          </Link>
          <Link to="/admin/cases" className={linkClass}>
            <ClipboardList aria-hidden="true" /> Cases
          </Link>
          <Link to="/admin/exports" className={linkClass}>
            <Download aria-hidden="true" /> Exports
          </Link>
          <Link to="/admin/account" className={linkClass}>
            <UserCog aria-hidden="true" /> My account
          </Link>
          {user?.is_superuser && (
            <>
              <Link to="/admin/agents" className={linkClass}>
                <UserCog aria-hidden="true" /> Agents
              </Link>
              <Link to="/admin/settings/general" className={linkClass}>
                <Settings aria-hidden="true" /> Settings
              </Link>
              <Link to="/admin/settings/services" className={linkClass}>
                <Settings aria-hidden="true" /> Service setup
              </Link>
              <Link to="/admin/settings/webhooks" className={linkClass}>
                <Settings aria-hidden="true" /> Webhooks
              </Link>
            </>
          )}
        </nav>
        <main id="admin-content" tabIndex={-1} className="min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
