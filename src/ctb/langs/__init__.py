from types import ModuleType

from ctb.langs import node, python

LANGS: dict[str, ModuleType] = {"python": python, "fastapi": python, "javascript": node, "express": node}
TECHS = tuple(LANGS)
WEB = frozenset({"fastapi", "express"})
RUBRICS = {
    "python": ("common", "python/python"),
    "fastapi": ("common", "python/python", "python/fastapi"),
    "javascript": ("common", "node/javascript"),
    "express": ("common", "node/javascript", "node/express"),
}


def lang(tech: str) -> ModuleType:
    return LANGS[tech]
