import { createElement, Fragment, type ReactNode } from "react"
import { cn } from "@/lib/utils"

const allowedTags = new Set([
  "p",
  "br",
  "strong",
  "em",
  "code",
  "h1",
  "h2",
  "h3",
  "h4",
  "ul",
  "ol",
  "li",
  "blockquote",
  "a",
])

function renderNode(node: Node, key: string): ReactNode {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent
  if (!(node instanceof HTMLElement)) return null
  const children = Array.from(node.childNodes).map((child, index) =>
    renderNode(child, `${key}-${index}`),
  )
  const tag = node.tagName.toLowerCase()
  if (!allowedTags.has(tag)) return <Fragment key={key}>{children}</Fragment>
  const props: Record<string, unknown> = { key }
  if (tag === "a") {
    const href = node.getAttribute("href") ?? ""
    if (/^https?:\/\//i.test(href)) {
      props.href = href
      props.rel = "nofollow noopener noreferrer"
      props.target = "_blank"
    }
  }
  return createElement(tag, props, children)
}

export function SafeHtml({
  html,
  className,
}: {
  html: string
  className?: string
}) {
  const document = new DOMParser().parseFromString(html, "text/html")
  return (
    <div className={cn("rich-text", className)}>
      {Array.from(document.body.childNodes).map((node, index) =>
        renderNode(node, String(index)),
      )}
    </div>
  )
}
