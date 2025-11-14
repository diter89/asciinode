class DiagramError(Exception):
    pass


class ConfigurationError(DiagramError):
    pass


class LayoutOverflowError(DiagramError):
    pass
