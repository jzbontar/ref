import os
import re
import time
import shutil
import itertools
from subprocess import Popen, PIPE

import meta
import extern


class Document:
    @classmethod
    def from_pdf(cls, fname):
        title = extract_title(fname)
        md = meta.fetch(title)

        doc = cls()
        doc.title = md.get('title', title)
        doc.authors = md.get('authors', '')
        doc.year = md.get('year', '')
        doc.added = time.time()

        # TODO: use pdftotext instead
        # cmd = ['pdftohtml', '-xml', '-stdout', fname]
        # xml = Popen(cmd, stdout=PIPE).communicate()[0].decode('utf8')
        # doc.text = extern.striptags(xml)

        dst = os.path.join(extern.DOCUMENT_DIR, os.path.basename(fname))
        shutil.copy(fname, dst)
        doc.fname = dst

        return doc

    def __str__(self):
        return str((self.title, self.authors, self.year))


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
            return title


if __name__ == '__main__':
    dir = '/home/jure/.local/share/data/Mendeley Ltd./Mendeley Desktop/' \
        'Downloaded'
    for base in os.listdir(dir):
        if os.path.splitext(base)[1] == '.pdf':
            fname = os.path.join(dir, base)
            print(base)
            print(extract_title(fname))
            #print(Document.from_pdf(fname))
            print()
