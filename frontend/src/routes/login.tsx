import { zodResolver } from "@hookform/resolvers/zod"
import { createFileRoute, Link, redirect } from "@tanstack/react-router"
import { LockKeyhole, Mountain } from "lucide-react"
import { useForm } from "react-hook-form"
import { z } from "zod"
import type { Body_login_login_access_token as AccessToken } from "@/client"
import { Brand } from "@/components/Brand"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PasswordInput } from "@/components/ui/password-input"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"

const schema = z.object({
  username: z.email("Enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
}) satisfies z.ZodType<AccessToken>

export const Route = createFileRoute("/login")({
  component: LoginPage,
  beforeLoad: () => {
    if (isLoggedIn()) throw redirect({ to: "/admin" })
  },
  head: () => ({ meta: [{ title: "Staff login — Tahr Desk" }] }),
})

function LoginPage() {
  const { loginMutation } = useAuth()
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { username: "", password: "" },
  })
  return (
    <main className="grid min-h-dvh bg-paper lg:grid-cols-2">
      <section className="relative hidden overflow-hidden bg-spruce p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <Brand className="[&_span]:text-white" />
        <div className="relative z-10 max-w-lg">
          <p className="eyebrow !text-amber">Staff workspace</p>
          <h2 className="text-5xl font-black leading-tight">
            Every request has a clear next step.
          </h2>
          <p className="mt-5 text-lg leading-8 text-white/75">
            Triage, coordinate, and document civic service work in one focused
            desk.
          </p>
        </div>
        <Mountain
          className="absolute -bottom-20 -right-20 size-96 text-white/8"
          aria-hidden="true"
        />
        <p className="text-sm text-white/75">Authorized Pinehaven staff only</p>
      </section>
      <section className="flex items-center justify-center p-5 sm:p-10">
        <div className="w-full max-w-md">
          <Brand className="mb-10 lg:hidden" />
          <div className="surface p-6 sm:p-9">
            <LockKeyhole
              className="mb-4 size-9 text-mineral"
              aria-hidden="true"
            />
            <h1 className="text-3xl font-black">Staff login</h1>
            <p className="mt-2 text-ink/70">
              Sign in with your staff credentials.
            </p>
            <form
              className="mt-7 grid gap-5"
              onSubmit={form.handleSubmit((values) =>
                loginMutation.mutate(values),
              )}
            >
              <div>
                <label className="field-label" htmlFor="username">
                  Email address
                </label>
                <Input
                  id="username"
                  type="email"
                  autoComplete="username"
                  {...form.register("username")}
                  aria-invalid={!!form.formState.errors.username}
                />
                {form.formState.errors.username && (
                  <p className="field-error">
                    {form.formState.errors.username.message}
                  </p>
                )}
              </div>
              <div>
                <label className="field-label" htmlFor="password">
                  Password
                </label>
                <PasswordInput
                  id="password"
                  autoComplete="current-password"
                  {...form.register("password")}
                  aria-invalid={!!form.formState.errors.password}
                />
                {form.formState.errors.password && (
                  <p className="field-error">
                    {form.formState.errors.password.message}
                  </p>
                )}
              </div>
              <Button
                type="submit"
                size="lg"
                className="w-full"
                disabled={loginMutation.isPending}
              >
                {loginMutation.isPending ? "Signing in…" : "Sign in"}
              </Button>
            </form>
            <Link
              to="/"
              className="mt-6 flex min-h-11 items-center justify-center rounded-lg font-bold text-mineral hover:underline"
            >
              Return to Tahr Desk
            </Link>
          </div>
        </div>
      </section>
    </main>
  )
}
