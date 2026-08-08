import { beforeEach, describe, expect, it } from "vitest"
import { isLoggedIn } from "./useAuth"

describe("isLoggedIn", () => {
  beforeEach(() => sessionStorage.clear())

  it("uses session storage and never persistent local storage", () => {
    expect(isLoggedIn()).toBe(false)
    sessionStorage.setItem("access_token", "ephemeral-token")
    expect(isLoggedIn()).toBe(true)
    expect(localStorage.getItem("access_token")).toBeNull()
  })
})
