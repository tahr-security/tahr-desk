import { describe, expect, it } from "vitest"
import { reportSchema } from "./schema"

const validReport = {
  category_id: "20000000-0000-4000-8000-000000000001",
  location_text: "12 Cedar Avenue",
  subject: "Raised sidewalk panel",
  description: "One concrete panel is raised and creates a tripping hazard.",
  reporter_name: "Avery Resident",
  reporter_email: "avery@example.com",
}

describe("reportSchema", () => {
  it("accepts a complete civic request", () => {
    expect(reportSchema.safeParse(validReport).success).toBe(true)
  })

  it("returns field-specific errors for incomplete reports", () => {
    const result = reportSchema.safeParse({
      ...validReport,
      category_id: "",
      description: "too short",
      reporter_email: "invalid",
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.flatten().fieldErrors.category_id).toContain(
        "Choose a service",
      )
      expect(result.error.flatten().fieldErrors.description).toContain(
        "Add at least 20 characters of detail",
      )
      expect(result.error.flatten().fieldErrors.reporter_email).toContain(
        "Enter a valid email address",
      )
    }
  })
})
