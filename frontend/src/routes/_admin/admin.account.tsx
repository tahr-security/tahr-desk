import { useMutation } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"
import { UsersService } from "@/client"
import { Button } from "@/components/ui/button"
import { PasswordInput } from "@/components/ui/password-input"
import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_admin/admin/account")({
  component: AccountPage,
  head: () => ({ meta: [{ title: "My account — Tahr Desk" }] }),
})

function AccountPage() {
  const { user, logout } = useAuth()
  const [current, setCurrent] = useState("")
  const [next, setNext] = useState("")
  const mutation = useMutation({
    mutationFn: () =>
      UsersService.updatePasswordMe({
        body: { current_password: current, new_password: next },
      }),
    onSuccess: logout,
  })
  return (
    <div className="max-w-2xl">
      <p className="eyebrow">Profile</p>
      <h1 className="text-4xl font-black">My account</h1>
      <section className="surface mt-7 p-6">
        <h2 className="text-xl font-black">Account details</h2>
        <dl className="mt-4 grid gap-3 sm:grid-cols-2">
          <div>
            <dt className="text-sm text-ink/70">Name</dt>
            <dd className="font-bold">{user?.full_name}</dd>
          </div>
          <div>
            <dt className="text-sm text-ink/70">Role</dt>
            <dd className="font-bold capitalize">{user?.role}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-sm text-ink/70">Email</dt>
            <dd className="font-bold">{user?.email}</dd>
          </div>
        </dl>
      </section>
      <form
        className="surface mt-5 grid gap-5 p-6"
        onSubmit={(event) => {
          event.preventDefault()
          mutation.mutate()
        }}
      >
        <h2 className="text-xl font-black">Change password</h2>
        <div>
          <label className="field-label" htmlFor="current-password">
            Current password
          </label>
          <PasswordInput
            id="current-password"
            autoComplete="current-password"
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
          />
        </div>
        <div>
          <label className="field-label" htmlFor="new-password">
            New password
          </label>
          <PasswordInput
            id="new-password"
            autoComplete="new-password"
            value={next}
            onChange={(event) => setNext(event.target.value)}
          />
        </div>
        {mutation.isError && (
          <p className="field-error" role="alert">
            Password could not be changed. Check the current password and
            requirements.
          </p>
        )}
        <Button
          type="submit"
          disabled={
            current.length < 8 || next.length < 12 || mutation.isPending
          }
        >
          {mutation.isPending ? "Updating…" : "Update password and sign out"}
        </Button>
      </form>
    </div>
  )
}
