"""City registry: looks up city configurations by id.

`discover_cities` builds the registry by importing every module of this package
and collecting its CITY constant. Adding a city is therefore one new file; no
existing code is edited (open/closed principle).
"""

import importlib
import pkgutil
from collections.abc import Iterable

import cities
from cities.base import CityConfig


class UnknownCityError(LookupError):
    pass


class CityRegistry:
    def __init__(self, configs: Iterable[CityConfig]) -> None:
        self._configs: dict[str, CityConfig] = {}
        for config in configs:
            if config.id in self._configs:
                raise ValueError(f"city id defined twice: {config.id}")
            self._configs[config.id] = config

    def get(self, city_id: str) -> CityConfig:
        try:
            return self._configs[city_id]
        except KeyError:
            known = ", ".join(sorted(self._configs))
            raise UnknownCityError(f"unknown city '{city_id}' (known: {known})") from None

    def all(self) -> tuple[CityConfig, ...]:
        return tuple(self._configs[city_id] for city_id in sorted(self._configs))


def discover_cities() -> CityRegistry:
    configs = []
    for module_info in pkgutil.iter_modules(cities.__path__):
        module = importlib.import_module(f"cities.{module_info.name}")
        config = getattr(module, "CITY", None)
        if isinstance(config, CityConfig):
            configs.append(config)
    return CityRegistry(configs)
