import uuid
from datetime import datetime
from html.parser import HTMLParser

from sqlalchemy.orm import Session


class ButtonParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.buttons: list[tuple[dict[str, str], str]] = []
        self._attributes: dict[str, str] | None = None
        self._text = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "button":
            self._attributes = {name: value or "" for name, value in attrs}
            self._text = ""

    def handle_data(self, data: str) -> None:
        if self._attributes is not None:
            self._text += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "button" and self._attributes is not None:
            self.buttons.append((self._attributes, self._text.strip()))
            self._attributes = None


def test_player_next_button_loads_the_next_ratings_page(configured_site) -> None:
    client, engine, tables_module, match_id, _, _, _ = configured_site
    player_id = uuid.UUID(int=1)

    with Session(engine) as session:
        session.add_all(
            [
                tables_module.PlayerRating(
                    id=uuid.UUID(int=600 + index),
                    match_id=match_id,
                    player_id=player_id,
                    rating=1600 + index,
                    created_at=datetime(2024, 1, 2, 12),
                )
                for index in range(10)
            ]
        )
        session.commit()

    page = client.get(f"/player/{player_id}")
    assert page.status_code == 200

    parser = ButtonParser()
    parser.feed(page.text)
    next_buttons = [attributes for attributes, label in parser.buttons if label == "Next"]
    assert len(next_buttons) == 1
    next_page_url = next_buttons[0]["hx-post"]
    expected_next_page_url = f"/player/{player_id}/ratings/2"

    assert next_page_url == expected_next_page_url
    next_page = client.post(next_page_url)
    assert next_page.status_code == 200
    assert "Page 2 of 2" in next_page.text
