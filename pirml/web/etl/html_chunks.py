from __future__ import annotations

import html.parser
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pirml.web.types import ChunkRow


class WebHTMLParser(html.parser.HTMLParser):
    def __init__(self, *, url: str, doc_sha256: str, source_rank: int, doc_rank: int):
        super().__init__()
        self.url = url
        self.doc_sha256 = doc_sha256
        self.source_rank = source_rank
        self.doc_rank = doc_rank

        self.chunks: list[ChunkRow] = []
        self._tag_stack: list[str] = []
        self._current_chunk_data: list[str] = []
        self._current_kind: str = "text"
        self._chunk_counter = 0

        self._ignored_tags = {"script", "style", "noscript", "iframe", "svg", "canvas"}
        self._block_tags = {
            "p",
            "li",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "title",
            "div",
            "section",
            "article",
            "header",
            "footer",
            "aside",
            "nav",
            "tr",
            "td",
            "th",
            "blockquote",
        }

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        tag = tag.lower()
        self._tag_stack.append(tag)

        if tag in self._ignored_tags:
            return

        if tag == "meta":
            attr_dict = dict(attrs)
            name = attr_dict.get("name") or attr_dict.get("property")
            content = attr_dict.get("content")
            if name and content and any(k in name.lower() for k in ("desc", "title", "keyw")):
                self._emit_chunk(kind="meta", text=f"{name}: {content}", path_hint=f"meta[{name}]")
            return

        if tag in self._block_tags:
            self._flush_current_chunk()
            self._current_kind = tag

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()

        if tag in self._block_tags:
            self._flush_current_chunk()

    def handle_data(self, data: str):
        if any(t in self._ignored_tags for t in self._tag_stack):
            return

        clean_data = data.strip()
        if clean_data:
            self._current_chunk_data.append(clean_data)

    def _flush_current_chunk(self):
        text = " ".join(self._current_chunk_data).strip()
        if text:
            # Simple path hint from tag stack
            path_hint = ">".join(self._tag_stack[-3:]) if self._tag_stack else self._current_kind
            self._emit_chunk(kind=self._current_kind, text=text, path_hint=path_hint)
        self._current_chunk_data = []

    def _emit_chunk(self, kind: str, text: str, path_hint: str):
        # Max 800 chars per C2.obj requirement
        text = text[:800]
        if not text:
            return

        chunk_id = f"ck{self._chunk_counter:04d}"
        self._chunk_counter += 1

        chunk: ChunkRow = {
            "url": self.url,
            "doc_sha256": self.doc_sha256,
            "chunk_id": chunk_id,
            "kind": kind,
            "path_hint": path_hint,
            "text": text,
            "score": 0.0,  # To be filled by scorer
            "source_rank": self.source_rank,
            "doc_rank": self.doc_rank,
        }
        self.chunks.append(chunk)


def extract_html_chunks(
    html_content: str, *, url: str, doc_sha256: str, source_rank: int, doc_rank: int
) -> list[ChunkRow]:
    parser = WebHTMLParser(
        url=url, doc_sha256=doc_sha256, source_rank=source_rank, doc_rank=doc_rank
    )
    try:
        parser.feed(html_content)
        parser.close()
    except Exception:
        # Fallback will handle it if it yields low coverage, but we don't want to crash here
        pass

    return parser.chunks


__all__ = ["extract_html_chunks"]
