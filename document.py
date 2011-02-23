import os
import re
import time
import shutil
import itertools
import time
from subprocess import Popen, PIPE

import extern


class Document:
    @classmethod
    def from_pdf(cls, fname):
        title = extract_title(fname)
        md = fetch_bibtex(title)

        # TODO: use pdftotext instead
        # cmd = ['pdftohtml', '-xml', '-stdout', fname]
        # xml = Popen(cmd, stdout=PIPE).communicate()[0].decode('utf8')
        # doc.text = extern.striptags(xml)

        dst = os.path.join(extern.DOCUMENT_DIR, os.path.basename(fname))
        shutil.copy(fname, dst)
        doc.fname = dst

        return doc

    @classmethod
    def from_bibtex(cls, bib):
        doc = cls()
        if not bib.strip():
            return doc
        for line in map(str.strip, bib.splitlines()):
            match = re.match(r'@([^{]+){([^,]+)', line)
            if match:
                type, cite = match.groups()
                doc.type = type
                doc.cite = cite
                continue
            match = re.match(r'([^=]+)={+(.+?)}+,', line)
            if match:
                name, value = match.groups()
                setattr(doc, name, value)
        return doc


def extract_title(fname):
    cmd = ['pdftohtml', '-xml', '-stdout', '-l', '1', fname]
    xml = Popen(cmd, stdout=PIPE).communicate()[0].decode('utf8')

    # pdftohtml has trouble with the letters 'fi'
    xml = xml.replace(chr(64257), 'fi')

    fontspec = re.findall(r'<fontspec id="(\d+)" size="(-?\d+)"', xml)
    font_size = {id: int(size) for id, size in fontspec}

    chunks = []
    for id, text in re.findall(r'font="(\d+)">(.*?)</text>', xml):
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
            #title = re.sub('\W+', ' ', title)
            return title


def fetch_bibtex(title):
    if not title:
        return ''

    url = '/scholar?q=allintitle:{}'.format(urllib.parse.quote(title))
    html = extern.scholar_read(url)

    match = re.search(r'<a href="(/scholar.bib[^"]+)', html)
    if not match:
        return ''

    return extern.scholar_read(match.group(1))


def scholar_read(url):
    time.sleep(1)
    id = ''.join(random.choice('0123456789abcdef') for i in range(16))
    cookie = 'GSP=ID={}:CF=4;'.format(id)
    h = {'User-agent': 'Mozilla/5.0', 'Cookie': cookie}
    req = urllib.request.Request('http://scholar.google.com' + url, headers=h)
    return unescape(urllib.request.urlopen(req).read().decode('utf8'))


if __name__ == '__main__':
    # fname = '/home/jure/tmp/10.1.1.73.7062.pdf'
    # title = extract_title(fname)
    # bib = fetch_bibtex(title)
    # doc = Document.from_bibtex(bib)
    # print(title)
    # print(doc.__dict__)

    dir = '/home/jure/.local/share/data/Mendeley Ltd./Mendeley Desktop/' \
        'Downloaded'
    for base in os.listdir(dir):
        if os.path.splitext(base)[1] == '.pdf':
            fname = os.path.join(dir, base)
            print(base)
            title = extract_title(fname)
            bibtex = fetch_bibtex(title)
            doc = Document.from_bibtex(bib)

            print(title)
            print(bib)
            print(doc.__dict__)
            print()
