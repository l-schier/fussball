from pages.layout import Layout


class PageContentWidth(Layout):
    def __init__(self) -> None:
        super().__init__()
        self.max_width = "max-w-7xl"
