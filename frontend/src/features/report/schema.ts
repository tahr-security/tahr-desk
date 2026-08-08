import { z } from "zod"

export const reportSchema = z.object({
  category_id: z.string().min(1, "Choose a service"),
  location_text: z.string().min(5, "Enter a specific location").max(300),
  subject: z.string().min(5, "Summarize the issue").max(160),
  description: z
    .string()
    .min(20, "Add at least 20 characters of detail")
    .max(5000),
  reporter_name: z.string().min(2, "Enter your name").max(120),
  reporter_email: z.email("Enter a valid email address"),
})

export type ReportFormValues = z.infer<typeof reportSchema>
