#! /usr/bin/env python2

from subprocess import Popen, PIPE
import collections
import filecmp
import htmlentitydefs
import os
import random
import re
import shutil
import sqlite3
import sys
import time
import itertools
import urllib2


BASE_DIR = os.path.expanduser('~/.ref/')
DOCUMENT_DIR = os.path.join(BASE_DIR, 'documents/')


def import_mendeley():
    dir = u'/home/jure/.mendeley'
    for base in os.listdir(dir):
        insert_document(os.path.join(dir, base))


def create_tables():
    con.execute('''CREATE TABLE IF NOT EXISTS documents 
        (bibtex TEXT, author TEXT, title TEXT, year INTEGER, journal TEXT, 
        rating INTEGER, filename TEXT, fulltext TEXT, tags TEXT,
        added TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    

def select_documents(fields, rowids=None, where=None, args=()):
    assert not (rowids and where)

    sql = 'SELECT {} FROM documents'.format(','.join(fields))
    if rowids:
       sql += ' WHERE rowid in ({})'.format(','.join(map(str, rowids)))
    elif where:
       sql += ' WHERE ' + where
    sql += ' ORDER BY rowid DESC'
    return map(dict, con.execute(sql, args))


def update_document(doc):
    doc.update(parse_bibtex(doc['bibtex']))
    rename_document(doc)
    con.execute('''UPDATE documents SET 
        bibtex=?,author=?,title=?,year=?,journal=?,rating=?,filename=?,tags=?
        WHERE rowid=?''',
        (doc['bibtex'], doc['author'], doc['title'], doc['year'],
        doc['journal'], doc['rating'], doc['filename'], doc['tags'],
        doc['rowid']))
        
    
def insert_document(fname):
    if os.path.splitext(fname)[1] != '.pdf':
        return

    for base2 in os.listdir(DOCUMENT_DIR):
        fname2 = os.path.join(DOCUMENT_DIR, base2)
        if filecmp.cmp(fname, fname2):
            print 'Could not insert. Duplicate ({})?'.format(fname2)
            return 

    doc = collections.defaultdict(unicode)
    cmd = ['pdftotext', '-enc', 'ASCII7', fname, '-']
    doc['fulltext'] = Popen(cmd, stdout=PIPE, stderr=PIPE).communicate()[0].decode('ascii')
    doc['bibtex'] = fetch_bibtex(extract_title(fname))
    doc['filename'] = os.path.join(DOCUMENT_DIR, 'tmp.pdf')
    
    cur = con.execute('''INSERT INTO documents
        (bibtex,fulltext) VALUES (?,?)''', 
        (doc['bibtex'], doc['fulltext']))
    doc['rowid'] = cur.lastrowid
    shutil.copy(fname, doc['filename'])
    update_document(doc)
    print '+', fname
    return doc['rowid']


def delete_document(rowid):
    doc = select_documents(('rowid', 'filename'), rowids=(rowid,))[0]
    con.execute('DELETE FROM documents WHERE rowid=?', (doc['rowid'],))
    try:
        os.remove(os.path.join(DOCUMENT_DIR, doc['filename']))
    except OSError:
        pass


def rename_document(doc):
    if doc['author'].count(', ') > 2:
        author = doc['author'].split(', ')[0] + ' et al.'
    else:
        author = doc['author']
    fields = (author, doc['year'], doc['title'], str(doc['rowid'])) 
    base = ' - '.join(filter(None, fields))
    base += '.' + doc['filename'].split('.')[-1]

    if doc['filename'] != base:
        src = os.path.join(DOCUMENT_DIR, doc['filename'])
        dst = os.path.join(DOCUMENT_DIR, base)
        if os.path.isfile(dst):
            print 'Could not rename. Duplicate?'
            return
        os.rename(src, dst)
        doc['filename'] = base
    

def get_tags():
    tags = set()
    for row in con.execute('SELECT tags FROM documents'):
        if row['tags']:
            tags.update(tag.strip() for tag in row['tags'].split(';'))
    return tags


def parse_bibtex(bibtex):
    d = collections.defaultdict(unicode)
    reg = r'^\s*(title|author|year|journal)={*(.+?)}*,?$'
    d.update(dict(re.findall(reg, bibtex, re.MULTILINE)))
    for k, v in d.items():
        d[k] = re.sub('[^-\w ,:]', '', v)
    d['author'] = ', '.join(a[:a.find(',')]
        for a in d['author'].split(' and '))
    return d


def extract_title(fname):
    cmd = ['pdftohtml', '-enc', 'ASCII7', '-xml', '-stdout', '-l', '1', fname]
    xml = Popen(cmd, stdout=PIPE, stderr=PIPE).communicate()[0].decode('ascii')

    fontspec = re.findall(r'<fontspec id="([^"]+)" size="([^"]+)"', xml)
    font_size = {id: int(size) for id, size in fontspec}

    chunks = []
    for id, text in re.findall(r'font="([^"]+)">(.*)</text>', xml):
        chunks.append((font_size[id], id, striptags(text).strip()))

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
    url = '/scholar?q=allintitle:' + urllib2.quote(title.encode('utf8'))
    html = scholar_read(url)
    match = re.search(r'<a href="(/scholar.bib[^"]+)', html)
    if not match:
        return ''
    return scholar_read(match.group(1))


def delay(n, interval):
    def decorator(f):
        call_times = collections.deque()
        def helper(*args):
            if len(call_times) == n:
                time.sleep(max(0, interval + call_times.pop() - time.time()))
            call_times.appendleft(time.time())
            return f(*args)
        return helper
    return decorator


@delay(4, 10)
def scholar_read(url):
    id = ''.join(random.choice('0123456789abcdef') for i in range(16))
    cookie = 'GSP=ID={}:CF=4;'.format(id)
    h = {'User-agent': 'Mozilla/5.0', 'Cookie': cookie}
    req = urllib2.Request('http://scholar.google.com' + url, headers=h)
    return unescape(urllib2.urlopen(req).read().decode('utf8'))


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


for dir in (BASE_DIR, DOCUMENT_DIR):
    if not os.path.exists(dir):
        os.mkdir(dir)

con = sqlite3.connect(os.path.join(BASE_DIR, 'db.sqlite3'))
con.isolation_level = None
con.row_factory = sqlite3.Row
create_tables()

#import_mendeley()

if __name__ == '__main__':
    import sys

    for fname in sys.argv[1:]:
        insert_document(fname)
