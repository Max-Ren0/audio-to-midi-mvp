from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_PAGES = [
    "outputs/portfolio-preview/index.html",
    "outputs/portfolio-pdf/index.html",
]


class PageLinks(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.ids = set()
        self.links = []
        self.feed(path.read_text(encoding="utf-8"))
        self.close()

    def handle_starttag(self, tag, attrs):
        line, _ = self.getpos()
        for name, value in attrs:
            if name == "id":
                self.ids.add(value)
            elif name in {"href", "src"}:
                self.links.append((line, name, value))


def link_error(page, path, attribute, value):
    if not value:
        return "请提供有效的链接或资源地址"
    if "{" in value or "}" in value:
        return "请把未替换的占位符改为实际地址"

    try:
        url = urlsplit(value)
        port = url.port
    except ValueError:
        return "请修正 URL 的主机或端口格式"

    if url.scheme or url.netloc:
        if (
            url.scheme not in {"http", "https", ""}
            or not url.hostname
            or port == 0
            or any(char.isspace() or char == "\\" for char in value)
        ):
            return "请使用格式有效的 HTTP(S) URL"
        return None

    target = path
    if url.path:
        relative_path = unquote(url.path)
        if relative_path.startswith("/"):
            target = REPO_ROOT / relative_path.lstrip("/")
        else:
            target = path.parent / relative_path
        target = target.resolve()
        if not target.is_relative_to(REPO_ROOT) or not target.is_file():
            return "请链接到仓库中存在的文件，相对路径从当前 HTML 所在目录起算"

    if attribute == "href" and url.fragment:
        if target == path:
            ids = page.ids
        elif target.suffix.lower() in {".html", ".htm"}:
            ids = PageLinks(target).ids
        else:
            return None
        if unquote(url.fragment) not in ids:
            return "请修正锚点名称，或在目标 HTML 中添加对应的 id"
    return None


@pytest.mark.parametrize("filename", PORTFOLIO_PAGES)
def test_portfolio_links(filename):
    path = REPO_ROOT / filename
    page = PageLinks(path)
    errors = []
    for line, attribute, value in page.links:
        error = link_error(page, path, attribute, value)
        if error:
            errors.append(f"{filename}:{line} {attribute}={value!r}：{error}")
    assert not errors, "\n" + "\n".join(errors)
