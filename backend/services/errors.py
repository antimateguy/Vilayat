"""Errors the services raise for requests that refer to something that does not exist."""


class NotFoundError(LookupError):
    """The request names a city, campus or employer that is not in the catalogue."""


class InvalidRequestError(ValueError):
    """The request is well-formed but asks for something that makes no sense."""
