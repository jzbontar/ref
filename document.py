from subprocess import Popen, PIPE
import itertools
import os
import random
import re
import sys
import time
import urllib
import urllib2

import extern


def extract_title(fname):
    cmd = ['pdftohtml', '-xml', '-stdout', '-l', '1', fname]
    xml = Popen(cmd, stdout=PIPE).communicate()[0].decode()

    # pdftohtml has trouble with the letters 'fi'
    xml = xml.replace(unichr(64257), 'fi')

    fontspec = re.findall(r'<fontspec id="([^"]+)" size="([^"]+)"', xml)
    font_size = {id: int(size) for id, size in fontspec}

    chunks = []
    for id, text in re.findall(r'font="([^"]+)">(.*)</text>', xml):
        chunks.append((font_size[id], id, extern.striptags(text).strip()))

    groups = []
    for size_id, group in itertools.groupby(chunks, lambda xs: xs[:2]):
        size, id = size_id
        text_size = size + text.startswith('<b>') * 0.5
        groups.append((text_size, list(group)))

    for _, group in sorted(groups, key=lambda xs: xs[0], reverse=True):
        title = ' '.join(map(lambda xs: xs[2], group)).strip()
        bad = ('abstract', 'introduction', 'relatedwork')
        if len(title) >= 5 and re.sub(r'[\d\s]', '', title).lower() not in bad:
            return title


def fetch_bibtex(title):
    if not title:
        return ''
    url = '/scholar?q=allintitle:{}'.format(urllib.quote(title.encode('utf8')))
    html = scholar_read(url)
    match = re.search(r'<a href="(/scholar.bib[^"]+)', html)
    if not match:
        return ''
    return scholar_read(match.group(1))


def scholar_read(url):
    time.sleep(8)
    id = ''.join(random.choice('0123456789abcdef') for i in range(16))
    cookie = 'GSP=ID={}:CF=4;'.format(id)
    h = {'User-agent': 'Mozilla/5.0', 'Cookie': cookie}
    req = urllib2.Request('http://scholar.google.com' + url, headers=h)
    return extern.unescape(urllib2.urlopen(req).read().decode())


if __name__ == '__main__':
    sys.exit(0)
    if 1:
        extern.cur.execute('drop table if exists documents')
        extern.cur.execute('create table documents (bibtex text)')
        print('tables created')
    
    dir = '/home/jure/.mendeley'
    for base in os.listdir(dir):
        if os.path.splitext(base)[1] == '.pdf':
            fname = os.path.join(dir, base)
            print(base)
            title = extract_title(fname)
            print(title)
            bibtex = fetch_bibtex(title)
            print(bibtex)

            if bibtex:
                extern.cur.execute('insert into documents values (?)', (bibtex,))
