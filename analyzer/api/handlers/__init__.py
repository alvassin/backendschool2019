from .citizen import CitizenView
from .citizen_birthdays import CitizenBirthdaysView
from .citizens import CitizensView
from .imports import ImportsView
from .town_stat import TownAgeStatView


HANDLERS = (
    CitizenBirthdaysView, CitizensView, CitizenView, ImportsView,
    TownAgeStatView,
)
