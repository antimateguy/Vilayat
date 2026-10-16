"""Which OpenStreetMap tags count as which place category.

This one table drives both the download query and the classification of each
downloaded element, so the two cannot drift apart.
"""

from collections.abc import Mapping

from domain.place import PlaceCategory

TAG_CATEGORIES: dict[tuple[str, str], PlaceCategory] = {
    ("shop", "supermarket"): PlaceCategory.SUPERMARKET,
    ("amenity", "cafe"): PlaceCategory.CAFE,
    ("amenity", "library"): PlaceCategory.LIBRARY,
    ("leisure", "fitness_centre"): PlaceCategory.GYM,
    ("amenity", "restaurant"): PlaceCategory.RESTAURANT,
    # Fast-food outlets hire students the same way restaurants do.
    ("amenity", "fast_food"): PlaceCategory.RESTAURANT,
    ("amenity", "bar"): PlaceCategory.BAR,
    ("amenity", "pub"): PlaceCategory.BAR,
    ("shop", "clothes"): PlaceCategory.RETAIL,
    ("shop", "shoes"): PlaceCategory.RETAIL,
    ("shop", "department_store"): PlaceCategory.RETAIL,
    ("shop", "convenience"): PlaceCategory.RETAIL,
    ("shop", "bakery"): PlaceCategory.RETAIL,
    ("shop", "chemist"): PlaceCategory.RETAIL,
    ("shop", "electronics"): PlaceCategory.RETAIL,
    ("shop", "books"): PlaceCategory.RETAIL,
}

# Checked in this order when an element carries several of these keys.
TAG_KEYS = ("shop", "amenity", "leisure")


def classify(tags: Mapping[str, str]) -> PlaceCategory | None:
    """The category of an element, or None when it is not a place we track."""
    for key in TAG_KEYS:
        category = TAG_CATEGORIES.get((key, tags.get(key, "")))
        if category is not None:
            return category
    return None


def values_for(key: str) -> list[str]:
    return sorted(value for tag_key, value in TAG_CATEGORIES if tag_key == key)
