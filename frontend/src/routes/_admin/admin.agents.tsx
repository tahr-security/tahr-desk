import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Navigate } from "@tanstack/react-router"
import { useState } from "react"
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/StatusPanel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PasswordInput } from "@/components/ui/password-input"
import useAuth from "@/hooks/useAuth"
import { api } from "@/lib/api"

export const Route = createFileRoute("/_admin/admin/agents")({
  component: AgentsPage,
  head: () => ({ meta: [{ title: "Agents — Tahr Desk" }] }),
})

function AgentsPage() {
  const { user } = useAuth()
  const client = useQueryClient()
  const [email, setEmail] = useState("")
  const [name, setName] = useState("")
  const [password, setPassword] = useState("")
  const [passwords, setPasswords] = useState<Record<string, string>>({})
  const query = useQuery({
    queryKey: ["agents"],
    queryFn: api.admin.agents,
    enabled: !!user?.is_superuser,
  })
  const refresh = () => client.invalidateQueries({ queryKey: ["agents"] })
  const create = useMutation({
    mutationFn: () =>
      api.admin.createAgent({
        email,
        full_name: name,
        password,
        is_active: true,
      }),
    onSuccess: () => {
      setEmail("")
      setName("")
      setPassword("")
      refresh()
    },
  })
  const update = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      api.admin.updateAgent(id, {
        is_active: active,
        new_password: active ? passwords[id] : null,
      }),
    onSuccess: refresh,
  })
  const reset = useMutation({
    mutationFn: (id: string) =>
      api.admin.resetAgentPassword(id, passwords[id] ?? ""),
    onSuccess: refresh,
  })
  if (user && !user.is_superuser) return <Navigate to="/admin/forbidden" />
  if (query.isLoading) return <LoadingPanel label="Loading agents" />
  if (query.isError || !query.data)
    return <ErrorPanel retry={() => query.refetch()} />
  return (
    <div>
      <p className="eyebrow">Administration</p>
      <h1 className="text-4xl font-black">Staff agents</h1>
      <form
        className="surface mt-7 grid gap-4 p-6 lg:grid-cols-4 lg:items-end"
        onSubmit={(event) => {
          event.preventDefault()
          create.mutate()
        }}
      >
        <div>
          <label className="field-label" htmlFor="agent-name">
            Full name
          </label>
          <Input
            id="agent-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
        </div>
        <div>
          <label className="field-label" htmlFor="agent-email">
            Email
          </label>
          <Input
            id="agent-email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </div>
        <div>
          <label className="field-label" htmlFor="agent-password">
            Initial password
          </label>
          <PasswordInput
            id="agent-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </div>
        <Button
          type="submit"
          disabled={password.length < 12 || create.isPending}
        >
          {create.isPending ? "Creating…" : "Create active agent"}
        </Button>
      </form>
      {create.isError && (
        <p className="field-error mt-3" role="alert">
          Agent could not be created. Check for an existing email.
        </p>
      )}
      {query.data.count === 0 && (
        <div className="mt-6">
          <EmptyPanel title="No staff agents">
            <p>Create an agent to share the case queue.</p>
          </EmptyPanel>
        </div>
      )}
      <div className="mt-6 grid gap-4">
        {query.data.data.map((agent) => (
          <article
            className="surface grid gap-4 p-5 lg:grid-cols-[1fr_280px_auto] lg:items-end"
            key={agent.id}
          >
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-black">{agent.full_name}</h2>
                <span
                  className={`rounded-full px-2 py-1 text-xs font-bold ${agent.is_active ? "bg-green-100 text-green-800" : "bg-slate-100 text-slate-700"}`}
                >
                  {agent.is_active ? "Active" : "Inactive"}
                </span>
              </div>
              <p className="mt-1 text-sm text-ink/70">{agent.email}</p>
            </div>
            <div>
              <label className="field-label" htmlFor={`password-${agent.id}`}>
                {agent.is_active
                  ? "New password"
                  : "Password required to activate"}
              </label>
              <PasswordInput
                id={`password-${agent.id}`}
                value={passwords[agent.id] ?? ""}
                onChange={(event) =>
                  setPasswords({ ...passwords, [agent.id]: event.target.value })
                }
              />
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                disabled={
                  (passwords[agent.id]?.length ?? 0) < 12 || reset.isPending
                }
                onClick={() => reset.mutate(agent.id)}
              >
                Reset
              </Button>
              <Button
                variant={agent.is_active ? "destructive" : "default"}
                disabled={
                  update.isPending ||
                  (!agent.is_active && (passwords[agent.id]?.length ?? 0) < 12)
                }
                onClick={() =>
                  update.mutate({ id: agent.id, active: !agent.is_active })
                }
              >
                {agent.is_active ? "Deactivate" : "Activate"}
              </Button>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}
