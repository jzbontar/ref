import os
import re
import htmlentitydefs
import sqlite3


BASE_DIR = os.path.expanduser('~/.library/')
DOCUMENT_DIR = os.path.join(BASE_DIR, 'documents/')
DB_FILE = os.path.join(BASE_DIR, 'db.sqlite3')


def striptags(html):
    return re.sub(r'<[^>]+>', '', html)


def unescape_charref(ref):
    name = ref[2:-1]
    base = 10
    if name.startswith("x"):
        name = name[1:]
        base = 16
    return unichr(int(name, base))


def replace_entities(match):
    ent = match.group()
    if ent[1] == "#":
        return unescape_charref(ent)

    repl = htmlentitydefs.name2codepoint.get(ent[1:-1])
    if repl is not None:
        repl = unichr(repl)
    else:
        repl = ent
    return repl


def unescape(data):
    return re.sub(r"&#?[A-Za-z0-9]+?;", replace_entities, data)


conn = sqlite3.connect(DB_FILE)
conn.isolation_level = None

for dir in (BASE_DIR, DOCUMENT_DIR):
    if not os.path.exists(dir):
        os.mkdir(dir)
