import asyncio
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from importlib import import_module
from pathlib import Path

from uiwiz import PageRouter, UiwizApp, ui

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fussball"))
Layout = import_module("pages.layout").Layout


@dataclass
class RenderedLink:
    attributes: dict[str, str]
    navigation_classes: tuple[str, ...]
    text: str = ""


class NavigationLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.navigation_classes: list[str] = []
        self.links: list[RenderedLink] = []
        self.current_link: RenderedLink | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        if tag == "ul":
            self.navigation_classes.append(attributes.get("class", ""))
        elif tag == "a":
            self.current_link = RenderedLink(attributes, tuple(self.navigation_classes))

    def handle_data(self, data: str) -> None:
        if self.current_link is not None:
            self.current_link.text += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.current_link is not None:
            self.links.append(self.current_link)
            self.current_link = None
        elif tag == "ul":
            self.navigation_classes.pop()


def test_report_issue_link_is_available_in_desktop_and_mobile_navigation() -> None:
    app = UiwizApp(title="Navigation test", page_definition_class=Layout)
    router = PageRouter()

    @router.page("/navigation-test")
    async def navigation_test_page() -> None:
        ui.element("h1", "Navigation test page")

    app.include_router(router)

    async def request_page() -> tuple[int, str]:
        request_messages = [{"type": "http.request", "body": b"", "more_body": False}]
        response_messages: list[dict[str, object]] = []

        async def receive() -> dict[str, object]:
            return request_messages.pop()

        async def send(message: dict[str, object]) -> None:
            response_messages.append(message)

        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": "2.3"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": "/navigation-test",
                "raw_path": b"/navigation-test",
                "query_string": b"",
                "root_path": "",
                "headers": [(b"host", b"testserver")],
                "client": ("testclient", 50000),
                "server": ("testserver", 80),
            },
            receive,
            send,
        )
        status = next(message["status"] for message in response_messages if message["type"] == "http.response.start")
        body = b"".join(
            message.get("body", b"") for message in response_messages if message["type"] == "http.response.body"
        )
        return int(status), body.decode()

    status_code, response_text = asyncio.run(request_page())

    assert status_code == 200
    assert "Navigation test page" in response_text

    parser = NavigationLinkParser()
    parser.feed(response_text)
    report_links = [link for link in parser.links if link.text == "Report an issue"]

    assert len(report_links) == 2
    assert any("menu-horizontal" in " ".join(link.navigation_classes) for link in report_links)
    assert any("md:hidden" in " ".join(link.navigation_classes) for link in report_links)
    for link in report_links:
        assert link.attributes["href"] == "https://github.com/l-schier/fussball/issues/new"
        assert link.attributes["target"] == "_blank"
        assert {"noopener", "noreferrer"}.issubset(link.attributes["rel"].split())

    internal_links = {(link.text, link.attributes["href"]) for link in parser.links}
    assert {("Home", "/"), ("Matches", "/match"), ("Players", "/player")} <= internal_links
    rankings_links = [link for link in parser.links if link.text == "Team Rankings"]
    assert len(rankings_links) == 2
    assert any("menu-horizontal" in " ".join(link.navigation_classes) for link in rankings_links)
    assert any("md:hidden" in " ".join(link.navigation_classes) for link in rankings_links)
    assert all(link.attributes["href"] == "/team" for link in rankings_links)
