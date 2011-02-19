import extern
import html.entities
import os
import re
import urllib.parse
import urllib.request


def get_meta(html):
    d = {}
    reg = r'<meta (?:name|property)="([^"]+)" content="([^"]+)'
    for key, value in re.findall(reg, html):
        d.setdefault(key, []).append(value)
    return d


def meta_jucs(url):
    md = get_meta(extern.urlread(url))
    # remove hash from the first author
    md['article_authorstring'][0] = md['article_authorstring'][0][1:]
    return {
        'title': md['article_title'][0],
        'authors': md['article_authorstring'],
        'year': int(md['TimeCreated'][0][:4])
    }


def meta_citeseerx(url):
    if '/viewdoc/summary?' not in url:
        return

    html = extern.urlread(url)
    if 'No document with DOI' in html:
        return

    md = get_meta(html)
    return {
        'title': md['citation_title'][0],
        'authors': md['citation_authors'][0].split(', '),
        'year': int(md['citation_year'][0]),
    }


def meta_acm(url):
    md = get_meta(extern.urlread(url))
    return {
        'title': md['citation_title'][0],
        'authors': md['citation_authors'][0].split('; '),
        'year': int(md['citation_date'][0][-4:]),
    }


def meta_citeulike(url):
    if '/article/' not in url:
        return

    md = get_meta(extern.urlread(url))
    return {
        'title': md['dc:title'][0],
        'authors': md['dc:creator'],
        'year': int(md['dc:date'][0][:4]),
    }


def fetch(title):
    if not title:
        return {}

    url = 'http://google.com/search?q="{}"'.format(urllib.parse.quote(title))
    hits = re.findall(r'href="([^"]+)" class=l', extern.urlread(url))
    print(url)

    for url in hits:
        md = None
        urlp = urllib.parse.urlparse(url)
        if urlp.hostname == 'www.jucs.org':
            md = meta_jucs(url)
        elif urlp.hostname == 'citeseerx.ist.psu.edu':
            md = meta_citeseerx(url)
        elif urlp.hostname == 'portal.acm.org':
            md = meta_acm(url)
        elif urlp.hostname == 'www.citeulike.org':
            md = meta_citeulike(url)

        if md and extern.levenshtein(title.lower(), md['title'].lower()) <= 4:
            return md

    return {}
