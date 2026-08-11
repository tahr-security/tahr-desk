import AxeBuilder from "@axe-core/playwright"
import { expect, type Page, test } from "@playwright/test"

const adminEmail = process.env.FIRST_SUPERUSER ?? "demo-admin@tahr.ca"
const adminPassword = process.env.FIRST_SUPERUSER_PASSWORD
const pixel = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGN0yqtlYGBgYmBgYGBgAAAOCwExdVg2bgAAAABJRU5ErkJggg==",
  "base64",
)

async function login(page: Page) {
  test.skip(
    !adminPassword,
    "Full-stack administrator credentials are not configured",
  )
  await page.goto("/login")
  await page.getByLabel("Email address").fill(adminEmail)
  await page.getByLabel("Password", { exact: true }).fill(adminPassword!)
  await page.getByRole("button", { name: "Sign in" }).click()
  await expect(page).toHaveURL(/\/admin$/)
}

test("resident and staff complete a private case lifecycle", async ({
  page,
}) => {
  const unique = crypto.randomUUID().slice(0, 8)
  const email = `resident-${unique}@example.com`
  const subject = `Raised sidewalk ${unique}`

  await page.goto("/services")
  await expect(
    page.getByRole("heading", { name: "Service directory" }),
  ).toBeVisible()
  await page.goto("/report")
  await page.getByLabel("Service").selectOption({ index: 1 })
  await page.getByLabel("Location").fill("12 Cedar Avenue")
  await page.getByLabel("Short summary").fill(subject)
  await page
    .getByLabel("What did you observe?")
    .fill(
      "One concrete panel is raised enough to create a clear tripping hazard.",
    )
  await page.getByLabel(/Choose up to four/).setInputFiles({
    name: "sidewalk.png",
    mimeType: "image/png",
    buffer: pixel,
  })
  await page.getByLabel("Your name").fill("Avery Resident")
  await page.getByLabel("Email address").fill(email)
  await page.getByRole("button", { name: "Submit request" }).click()
  await expect(
    page.getByRole("heading", { name: "Keep this reference private" }),
  ).toBeVisible()
  const reference = await page
    .locator("code")
    .filter({ hasText: "TDK-" })
    .innerText()
  await expect(page).not.toHaveURL(/TDK-|resident-/)

  await page.goto("/track")
  await page.getByLabel("Case reference").fill(reference)
  await page.getByLabel("Email address").fill(email)
  await page.getByRole("button", { name: "View request" }).click()
  await expect(page.getByRole("heading", { name: subject })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Case photos" })).toBeVisible()

  await login(page)
  await page.goto("/admin/cases")
  await page.getByLabel("Search cases").fill(reference)
  await page.getByRole("link", { name: new RegExp(subject) }).click()
  await page.getByRole("button", { name: "Claim this case" }).click()
  await expect(page.getByText("Triaged", { exact: true })).toBeVisible()

  await page.getByLabel("Visibility").selectOption("private")
  await page.getByLabel("Message").fill("Internal inspection routing note")
  await page.getByRole("button", { name: "Save private note" }).click()
  await expect(page.getByText("Internal inspection routing note")).toBeVisible()
  await page.getByLabel("New status").selectOption("waiting_on_reporter")
  await page
    .getByLabel("Public summary")
    .fill("Please add the nearest house number.")
  await page.getByRole("button", { name: "Update status" }).click()
  await expect(
    page.getByText("Waiting on resident", { exact: true }),
  ).toBeVisible()

  await page.goto("/track")
  await page.getByLabel("Case reference").fill(reference)
  await page.getByLabel("Email address").fill(email)
  await page.getByRole("button", { name: "View request" }).click()
  await expect(page.getByText("Internal inspection routing note")).toHaveCount(
    0,
  )
  await page.getByLabel("Message").fill("The nearest house number is 12.")
  await page.getByRole("button", { name: "Send follow-up" }).click()
  await expect(page.getByText("In progress")).toBeVisible()

  await page.goto("/admin/cases")
  await page.getByLabel("Search cases").fill(reference)
  await page.getByRole("link", { name: new RegExp(subject) }).click()
  await page.getByLabel("New status").selectOption("resolved")
  await page
    .getByLabel("Public summary")
    .fill("Sidewalk panel reset and inspected.")
  await page.getByRole("button", { name: "Update status" }).click()
  await expect(page.getByText("Resolved", { exact: true })).toBeVisible()
  await page.getByLabel("New status").selectOption("closed")
  await page
    .getByLabel("Public summary")
    .fill("Request closed after completed repair.")
  await page.getByLabel("Closure reason").selectOption("resolved")
  await page.getByRole("button", { name: "Update status" }).click()
  await expect(page.getByText("Closed", { exact: true })).toBeVisible()
})

test("dashboard, export worker, keyboard, and major pages are accessible", async ({
  page,
}) => {
  await page.goto("/")
  const skip = page.getByRole("link", { name: "Skip to content" })
  await skip.focus()
  await expect(skip).toBeFocused()
  await page.keyboard.press("Enter")
  await expect(page).toHaveURL(/#main-content$/)
  for (const path of ["/", "/services", "/report", "/track", "/login"]) {
    await page.goto(path)
    await expect(page.locator("main")).toBeVisible()
    await expect(page.locator("h1").first()).toBeVisible()
    const results = await new AxeBuilder({ page }).analyze()
    expect(results.violations, `${path} accessibility violations`).toEqual([])
  }

  await login(page)
  await expect(
    page.getByRole("heading", { name: "Service desk overview" }),
  ).toBeVisible()
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  await page.goto("/admin/exports")
  await page.getByRole("button", { name: "Create CSV export" }).click()
  await expect(page.getByText("Case list CSV").first()).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Download" }).first(),
  ).toBeVisible({ timeout: 15_000 })
})

test("tracking failures stay generic and out of the URL", async ({ page }) => {
  await page.goto("/track")
  await page.getByLabel("Case reference").fill("TDK-00000000000000000000")
  await page.getByLabel("Email address").fill("nobody@example.com")
  await page.getByRole("button", { name: "View request" }).click()
  await expect(page.getByRole("alert")).toContainText(
    "No request matched those details",
  )
  await expect(page).not.toHaveURL(/TDK-|nobody/)
})
