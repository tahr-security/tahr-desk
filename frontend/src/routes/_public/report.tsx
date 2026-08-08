import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { CheckCircle2, Clipboard, ImagePlus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import type { CaseReceipt } from "@/client"
import { ErrorPanel, LoadingPanel } from "@/components/StatusPanel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { type ReportFormValues, reportSchema } from "@/features/report/schema"
import { api } from "@/lib/api"

export const Route = createFileRoute("/_public/report")({
  component: ReportPage,
  head: () => ({ meta: [{ title: "Report an issue — Tahr Desk" }] }),
})

function ReportPage() {
  const services = useQuery({ queryKey: ["services"], queryFn: api.services })
  const [photos, setPhotos] = useState<File[]>([])
  const [receipt, setReceipt] = useState<CaseReceipt | null>(null)
  const form = useForm<ReportFormValues>({
    resolver: zodResolver(reportSchema),
    defaultValues: {
      category_id: "",
      location_text: "",
      subject: "",
      description: "",
      reporter_name: "",
      reporter_email: "",
    },
  })
  const mutation = useMutation({
    mutationFn: (values: ReportFormValues) =>
      api.createCase({ ...values, submission_id: crypto.randomUUID(), photos }),
    onSuccess: setReceipt,
  })
  if (services.isLoading)
    return (
      <div className="page-container py-16">
        <LoadingPanel label="Preparing report form" />
      </div>
    )
  if (services.isError || !services.data)
    return (
      <div className="page-container py-16">
        <ErrorPanel retry={() => services.refetch()} />
      </div>
    )
  if (receipt)
    return (
      <div className="page-container py-16">
        <section
          className="surface mx-auto max-w-2xl p-7 text-center sm:p-10"
          aria-live="polite"
        >
          <CheckCircle2
            className="mx-auto size-14 text-pine"
            aria-hidden="true"
          />
          <p className="eyebrow mt-5">Request received</p>
          <h1 className="text-4xl font-black">Keep this reference private</h1>
          <p className="mt-3 text-ink/70">
            Use it with your email address to track the request.
          </p>
          <div className="mx-auto mt-7 flex max-w-md items-center justify-between rounded-xl border bg-paper p-4">
            <code className="text-lg font-black tracking-wide">
              {receipt.reference}
            </code>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Copy reference"
              onClick={() => navigator.clipboard.writeText(receipt.reference)}
            >
              <Clipboard />
            </Button>
          </div>
          <p className="mt-3 text-sm text-ink/70">
            Confirmation is associated with {receipt.reporter_email_masked}.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Button asChild>
              <Link to="/track">Track request</Link>
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                setReceipt(null)
                setPhotos([])
                form.reset()
              }}
            >
              Report another issue
            </Button>
          </div>
        </section>
      </div>
    )
  const errors = Object.values(form.formState.errors)
  return (
    <div className="page-container py-12 sm:py-16">
      <p className="eyebrow">New civic service request</p>
      <h1 className="text-4xl font-black sm:text-5xl">Report an issue</h1>
      <p className="mt-3 max-w-2xl text-lg text-ink/70">
        Share enough detail for staff to understand where the issue is and what
        you observed.
      </p>
      <form
        className="mt-9 grid gap-7 lg:grid-cols-[1fr_300px]"
        onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
      >
        <div className="surface grid gap-7 p-6 sm:p-9">
          {errors.length > 0 && (
            <div
              role="alert"
              tabIndex={-1}
              className="rounded-xl border border-destructive/35 bg-destructive/5 p-4"
            >
              <h2 className="font-black">Check the highlighted fields</h2>
              <p className="mt-1 text-sm">{errors[0]?.message}</p>
            </div>
          )}
          {mutation.isError && (
            <div
              role="alert"
              className="rounded-xl border border-destructive/35 bg-destructive/5 p-4"
            >
              Your request was not submitted. Please review it and try again.
            </div>
          )}
          <fieldset className="grid gap-5">
            <legend className="text-xl font-black">Service and location</legend>
            <div>
              <label className="field-label" htmlFor="category">
                Service
              </label>
              <select
                id="category"
                className="min-h-11 w-full rounded-md border bg-card px-3"
                {...form.register("category_id")}
              >
                <option value="">Choose a service</option>
                {services.data.data.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
              {form.formState.errors.category_id && (
                <p className="field-error">
                  {form.formState.errors.category_id.message}
                </p>
              )}
            </div>
            <Field
              label="Location"
              htmlFor="report-location"
              error={form.formState.errors.location_text?.message}
            >
              <Input
                id="report-location"
                {...form.register("location_text")}
                placeholder="Street address, intersection, park, or facility"
              />
            </Field>
          </fieldset>
          <fieldset className="grid gap-5">
            <legend className="text-xl font-black">Request details</legend>
            <Field
              label="Short summary"
              htmlFor="report-subject"
              error={form.formState.errors.subject?.message}
            >
              <Input id="report-subject" {...form.register("subject")} />
            </Field>
            <Field
              label="What did you observe?"
              htmlFor="report-description"
              error={form.formState.errors.description?.message}
            >
              <textarea
                id="report-description"
                className="text-area"
                {...form.register("description")}
              />
            </Field>
          </fieldset>
          <fieldset>
            <legend className="text-xl font-black">
              Photos{" "}
              <span className="text-sm font-normal text-ink/70">
                (optional)
              </span>
            </legend>
            <label className="mt-4 flex min-h-24 cursor-pointer items-center justify-center gap-3 rounded-xl border border-dashed bg-paper p-4 font-bold">
              <ImagePlus aria-hidden="true" />
              Choose up to four JPEG or PNG images
              <input
                className="sr-only"
                type="file"
                accept="image/jpeg,image/png"
                multiple
                onChange={(event) =>
                  setPhotos(Array.from(event.target.files ?? []).slice(0, 4))
                }
              />
            </label>
            {photos.length > 0 && (
              <p className="mt-2 text-sm text-ink/70">
                {photos.length} photo{photos.length === 1 ? "" : "s"} selected
              </p>
            )}
          </fieldset>
          <fieldset className="grid gap-5">
            <legend className="text-xl font-black">Contact</legend>
            <Field
              label="Your name"
              htmlFor="report-name"
              error={form.formState.errors.reporter_name?.message}
            >
              <Input
                id="report-name"
                autoComplete="name"
                {...form.register("reporter_name")}
              />
            </Field>
            <Field
              label="Email address"
              htmlFor="report-email"
              error={form.formState.errors.reporter_email?.message}
            >
              <Input
                id="report-email"
                type="email"
                autoComplete="email"
                {...form.register("reporter_email")}
              />
            </Field>
            <p className="text-sm text-ink/70">
              Your email is used only to retrieve and update this request.
            </p>
          </fieldset>
          <Button type="submit" size="lg" disabled={mutation.isPending}>
            {mutation.isPending ? "Submitting…" : "Submit request"}
          </Button>
        </div>
        <aside className="surface h-fit p-6 lg:sticky lg:top-24">
          <h2 className="text-lg font-black">Before you submit</h2>
          <ul className="mt-4 list-disc space-y-3 pl-5 text-sm leading-6 text-ink/70">
            <li>Do not use this service for emergencies.</li>
            <li>Include a precise, public location.</li>
            <li>Keep personal information out of descriptions and photos.</li>
            <li>Save the private reference shown after submission.</li>
          </ul>
        </aside>
      </form>
    </div>
  )
}

function Field({
  label,
  htmlFor,
  error,
  children,
}: {
  label: string
  htmlFor: string
  error?: string
  children: React.ReactNode
}) {
  return (
    <div>
      <label className="field-label" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
      {error && <p className="field-error">{error}</p>}
    </div>
  )
}
