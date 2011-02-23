import html
import html.entities
import os
import random
import re
import string
import urllib.request


BASE_DIR = os.path.expanduser('~/.library/')
DOCUMENT_DIR = os.path.join(BASE_DIR, 'documents/')


def striptags(html):
    return re.sub(r'<[^>]+>', '', html)


def unescape_charref(ref):
    name = ref[2:-1]
    base = 10
    if name.startswith("x"):
        name = name[1:]
        base = 16
    return chr(int(name, base))


def replace_entities(match):
    ent = match.group()
    if ent[1] == "#":
        return unescape_charref(ent)

    repl = html.entities.name2codepoint.get(ent[1:-1])
    if repl is not None:
        repl = chr(repl)
    else:
        repl = ent
    return repl


def unescape(data):
    return re.sub(r"&#?[A-Za-z0-9]+?;", replace_entities, data)


for dir in (BASE_DIR, DOCUMENT_DIR):
    if not os.path.exists(dir):
        os.mkdir(dir)
