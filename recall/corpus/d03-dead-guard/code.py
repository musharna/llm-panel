import pathlib


def render_image(path, config):
    """Render an <img> tag, honouring config.IMG_TYPES when it is available."""
    p = pathlib.Path(path)
    suffix = p.suffix.lstrip(".").lower()
    if hasattr(config, "IMG_TYPES"):
        mime = config.IMG_TYPES.get(suffix, "octet-stream")
    else:
        mime = "octet-stream"
    return f'<img src="data:image/{mime};base64,...">'


class Config:
    def __init__(self):
        IMG_TYPES = {"png": "png", "jpg": "jpeg"}
        self.name = "default"
