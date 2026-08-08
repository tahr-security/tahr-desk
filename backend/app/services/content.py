import nh3
from markdown_it import MarkdownIt

_markdown = MarkdownIt(
    "commonmark",
    {"html": False, "linkify": True, "typographer": False},
)

_allowed_tags = {
    "p",
    "br",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "h2",
    "h3",
    "h4",
    "blockquote",
    "code",
    "pre",
    "a",
}


def render_markdown(value: str) -> str:
    source = value.strip()
    rendered = _markdown.render(source)
    return nh3.clean(
        rendered,
        tags=_allowed_tags,
        attributes={"a": {"href", "title"}},
        url_schemes={"http", "https"},
        link_rel="nofollow noopener noreferrer",
    )
