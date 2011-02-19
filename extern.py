import re
import html
import os
import urllib.request


BASE_DIR = os.path.expanduser('~/.library/')
DOCUMENT_DIR = os.path.join(BASE_DIR, 'documents/')


def levenshtein(s, t):
    d = range(len(t) + 1)
    for i in range(len(s)):
        dd = [i + 1]
        for j in range(len(t)):
            dd.append(min(dd[j] + 1, d[j] + (s[i] != t[j]), d[j + 1] + 1))
        d = dd
    return dd[-1]


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


def urlread(url):
    return unescape(opener.open(url).read().decode('utf8'))


opener = urllib.request.build_opener()
opener.addheaders = [('User-agent', 'Mozilla/5.0')]

for dir in (BASE_DIR, DOCUMENT_DIR):
    if not os.path.exists(dir):
        os.mkdir(dir)
