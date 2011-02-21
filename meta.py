import re
import urllib.parse

import extern


def fetch(title):
    if not title:
        return {}

    url = 'http://scholar.google.com/scholar?q=allintitle:"{}"'
    html = extern.urlread(url.format(urllib.parse.quote(title)))

    match = re.search(r'related:([^:]+):', html)
    if not match:
        return ''

    url = 'http://scholar.google.com/scholar.bib?q=info:{}:scholar.google.com/&output=citation'
    return extern.urlread(url.format(match.group(1)))

if __name__ == '__main__':
    fetch('Plagiarism - A Survey')
