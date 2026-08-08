import { Link, Outlet } from "@tanstack/react-router"
import { Menu, X } from "lucide-react"
import { useState } from "react"
import { Brand } from "@/components/Brand"

const linkClass =
  "flex min-h-11 items-center rounded-lg px-3 font-bold text-ink/75 transition-colors hover:bg-pine/8 hover:text-ink focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-mineral/50 [&.active]:bg-pine/10 [&.active]:text-spruce"

export function PublicShell() {
  const [open, setOpen] = useState(false)
  return (
    <div className="min-h-dvh bg-paper text-ink">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="sticky top-0 z-40 border-b border-spruce/10 bg-card/95 backdrop-blur">
        <div className="page-container flex min-h-18 items-center justify-between gap-4">
          <Brand />
          <button
            type="button"
            className="grid size-11 place-items-center rounded-lg border border-spruce/15 md:hidden"
            aria-label={open ? "Close navigation" : "Open navigation"}
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X /> : <Menu />}
          </button>
          <nav
            aria-label="Main navigation"
            className={`${open ? "flex" : "hidden"} absolute inset-x-0 top-full flex-col border-b bg-card p-4 shadow-soft md:static md:flex md:flex-row md:border-0 md:bg-transparent md:p-0 md:shadow-none`}
          >
            <Link
              to="/report"
              className={linkClass}
              onClick={() => setOpen(false)}
            >
              Report an issue
            </Link>
            <Link
              to="/track"
              className={linkClass}
              onClick={() => setOpen(false)}
            >
              Track a request
            </Link>
            <Link
              to="/services"
              className={linkClass}
              onClick={() => setOpen(false)}
            >
              Services
            </Link>
          </nav>
        </div>
      </header>
      <main id="main-content" tabIndex={-1}>
        <Outlet />
      </main>
      <footer className="mt-16 border-t border-spruce/10 bg-card">
        <div className="page-container flex flex-col gap-5 py-8 text-sm text-ink/70 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-bold text-ink">Tahr Desk</p>
            <p>Clear requests. Accountable civic service.</p>
          </div>
          <Link to="/login" className={linkClass}>
            Staff login
          </Link>
        </div>
      </footer>
    </div>
  )
}
