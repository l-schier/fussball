import json
from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from uiwiz import UiwizApp, ui
from uiwiz.frame import Frame

class FussballApp(UiwizApp):
    async def handle_validation_error(self, request: Request, exc: RequestValidationError):
        fields_with_errors = [item.get("loc")[1] for item in exc.errors() if item.get("loc")[1] in exc.body]
        ok_fields = [item for item in exc.body.keys() if item not in fields_with_errors]

        Frame.get_stack().del_stack()
        Frame.get_stack()

        with ui.element().classes(self.error_classes) as toast:
            toast.attributes["id"] = "toast"
            toast.attributes["hx-swap-oob"] = "afterbegin"
            toast.attributes["hx-toast-data"] = json.dumps(
                jsonable_encoder(
                    {
                        "detail": exc.errors(),
                        "fieldErrors": fields_with_errors,
                        "fieldOk": ok_fields,
                    }
                )
            )
            html = ui.html("").classes("alert alert-error relative")
            html.tag = "span"
            html.attributes["hx-toast-data"] = json.dumps({"autoClose": self.auto_close_toast_error})
            html.attributes["hx-toast-delete-button"] = lambda: btn.id
            with html:
                with ui.col(gap="").classes("relative"):
                    for item in exc.errors():
                        ui.element(content=f"{item.get('loc')[1]}: {item.get('msg')}")
                if not self.auto_close_toast_error:
                    btn = ui.button("✕").classes("btn btn-sm btn-circle btn-ghost absolute right-2 top-2")

        html_content = Frame.get_stack().render()

        return HTMLResponse(
            content=html_content,
            status_code=400,
            headers={"cache-control": "no-store", "x-uiwiz-content": "page", "x-uiwiz-validation-error": "true"},
        )