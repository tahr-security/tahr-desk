import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { PriorityBadge, StatusBadge } from "./StatusBadge"
import { EmptyPanel, ErrorPanel, LoadingPanel } from "./StatusPanel"

describe("status components", () => {
  it("renders human-readable status and priority labels", () => {
    render(
      <>
        <StatusBadge status="waiting_on_reporter" />
        <PriorityBadge priority="urgent" />
      </>,
    )
    expect(screen.getByText("Waiting on resident")).toBeVisible()
    expect(screen.getByText("urgent")).toBeVisible()
  })

  it("announces loading, empty, and retry states", () => {
    const retry = vi.fn()
    const { rerender } = render(<LoadingPanel label="Loading cases" />)
    expect(screen.getByText("Loading cases…")).toBeVisible()
    expect(
      screen.getByText("Loading cases…").closest("[aria-busy]"),
    ).toHaveAttribute("aria-busy", "true")

    rerender(<EmptyPanel title="No cases">Try another filter.</EmptyPanel>)
    expect(screen.getByRole("status")).toHaveTextContent("Try another filter.")

    rerender(<ErrorPanel retry={retry} />)
    fireEvent.click(screen.getByRole("button", { name: "Try again" }))
    expect(retry).toHaveBeenCalledOnce()
    expect(screen.getByRole("alert")).toBeVisible()
  })
})
