from typing import Optional, override
from uiwiz import PageDefinition, ui
from uiwiz.svg.svg_handler import get_svg

pages = ["/", "/match", "/player"]

class Layout(PageDefinition):
    def __init__(self) -> None:
        """Layout

        A layout element that provides a consistent structure for the application.
        """
        super().__init__()
        self.drawer = None
        self._nav = None
        self.hide_on = "md"

    @override
    def content(self, _: ui.element) -> Optional[ui.element]:
        self.drawer = ui.drawer()
        with self.drawer:
            with self.drawer.drawer_content():
                self.nav(self.drawer)
                container = ui.container(padding="p-4")
            
            with self.drawer.drawer_side():
                with ui.element("ul").classes("flex-none block md:hidden w-full"):
                    for page in pages:
                        with ui.element("li"):
                            ui.link(page, page)
                    with ui.element("li"):
                        ui.themeSelector()

        return container

    def nav(self, drawer):
        with ui.element().classes(
            "sticky top-0 flex h-16 justify-center bg-opacity-90 backdrop-blur transition-shadow duration-100 [transform:translate3d(0,0,0)] shadow-sm z-40"
        ):
            with ui.nav().classes("bg-base-200"):
                with ui.element().classes("flex-1"):
                    with ui.label(for_=drawer.drawer_toggle).classes(
                        f"btn drawer-button {self.hide_on}:!hidden"
                    ):
                        ui.html(get_svg("menu"))
                with ui.element().classes(f"flex-none hidden {self.hide_on}:!block"):
                    with ui.element("ul").classes("menu menu-horizontal menu-md"):
                        for page in pages:
                            with ui.element("li"):
                                ui.link(page, page)
                        with ui.element("li"):
                            ui.themeSelector(["dark", "nord"])