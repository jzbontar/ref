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

    fonts = re.findall(r'<fontspec id="(\d+)" size="(\d+)"', xml)
    cmp_fonts = lambda id_size: int(id_size[1])
    fonts.sort(key=cmp_fonts, reverse=True)
    for size, font_group in itertools.groupby(fonts, cmp_fonts):
        font_group = {id for id, _ in font_group}

        title = ''
        for font, text in re.findall(r'font="(\d+)">(.*?)</text>', xml):
            text = extern.striptags(text)
            if font in font_group and len(title + text) >= 5:
                title += text
            elif title:
                break

        if title:
            return extern.striptags(title)


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
