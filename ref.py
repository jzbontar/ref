#! /usr/bin/env python2

from subprocess import Popen, PIPE
import collections
import filecmp
import htmlentitydefs
import itertools
import os
import random
import re
import shutil
import sqlite3
import struct
import sys
import time
import urllib2


BASE_DIR = os.path.expanduser('~/.ref/')
DOCUMENT_DIR = os.path.join(BASE_DIR, 'documents/')


def import_mendeley():
    dir = '/home/jure/.mendeley'
    for base in os.listdir(dir):
        print base
        insert_document(os.path.join(dir, base))


def create_test_data():
    import textwrap
    from random import randint, choice, sample, random

    def r(n, m, words=re.sub('\W+', ' ', open('tolstoy.txt').read()).split()):
        return ' '.join(choice(words) for i in range(randint(n, m)))

    all_tags = [r(1, 2) for i in range(100)]
    with con:
        for i in range(10000):
            print i

            title = r(5, 10)
            author = ' and '.join(r(1, 2) for _ in range(randint(1, 5)))
            year = str(randint(1800, 2000))
            journal = r(1, 5)
            rating = str(randint(1, 10))
            filename = r(10, 15)
            q = random()
            if q < 0.1:
                fulltext = r(50000, 200000)
            elif q < 0.9:
                fulltext = r(1000, 15000)
            else:
                fulltext = ''
            notes = textwrap.fill(r(0, 100))
            tags = '; '.join(sample(all_tags, randint(0, 3)))
            o = '\n  '.join(r(1, 1) + '=' + r(1, 5) for i in range(randint(0, 6)))
            bibtex = '''@book{{foo
  title={},
  author={},
  year={},
  journal={},
  {}
}}'''.format(title, author, year, journal, o)
            if random() < 0.1:
                title = author = year = journal = bibtex = None

            con.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?)',
                (bibtex, title, author, year, tags, rating, filename, notes))
            con.execute('INSERT INTO fts VALUES (?,?,?,?,?,?)',
                (title, author, journal, tags, notes, fulltext))


def optimize():
    with con:
        con.execute("INSERT INTO fts(fts) VALUES('optimize')")


def create_tables():
    with con:
        cur = con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        if cur.fetchone()[0] > 0:
            return
        con.execute('''CREATE TABLE documents 
            (bibtex TEXT, title TEXT, author TEXT, year INTEGER, tags TEXT, 
            rating INTEGER, filename TEXT, notes TEXT)''')
        con.execute('''CREATE VIRTUAL TABLE fts.fts USING fts4
            ({})'''.format(','.join(fts_columns)))


def select_documents(fields, rowids=None):
    sql = 'SELECT {} FROM documents'.format(','.join(fields))
    if rowids:
       sql += ' WHERE rowid in ({})'.format(','.join(map(str, rowids)))
    sql += ' ORDER BY rowid DESC'
    return con.execute(sql)


def search_documents(fields, query):
    hits = []
    cur = con.execute('''
        SELECT mi, {} FROM documents, (
            SELECT rowid, matchinfo(fts) as mi FROM fts
            WHERE fts MATCH ?) as fts
        WHERE documents.rowid=fts.rowid
        ORDER BY rowid DESC'''.format(','.join(fields)), 
        (query,))
    for row in cur:
        p, c = struct.unpack_from('ii', row[0])
        xs = struct.unpack_from('i' * (p * c * 3 + 2), row[0])[2::3]
        col_hits = [sum(xs[i::c]) for i in range(c)]
        hits.append((row, dict(zip(fts_columns, col_hits))))
    return hits


def update_document(doc):
    filename = get_filename(doc)
    if False and doc['filename'] != filename:
        src = os.path.join(DOCUMENT_DIR, doc['filename'])
        dst = os.path.join(DOCUMENT_DIR, filename)
        if os.path.isfile(dst):
            print 'Could not rename. Duplicate?'
            return
        os.rename(src, dst)
        doc['filename'] = filename

    with con:
        con.execute('''UPDATE documents SET 
            bibtex=?,author=?,title=?,year=?,rating=?,filename=?,tags=?,notes=?
            WHERE rowid=?''',
            (doc['bibtex'], doc['author'], doc['title'], doc['year'],
            doc['rating'], doc['filename'], doc['tags'], doc['notes'],
            doc['rowid']))
        con.execute('''UPDATE fts SET title=?,author=?,journal=?,tags=?
            WHERE rowid=?''',
            (doc['title'], doc['author'], doc['journal'], doc['tags'],
            doc['rowid']))
        
    
def insert_document(fname):
    if os.path.splitext(fname)[1] != '.pdf':
        return

    for base2 in os.listdir(DOCUMENT_DIR):
        fname2 = os.path.join(DOCUMENT_DIR, base2)
        if filecmp.cmp(fname, fname2):
            print 'Could not insert. Duplicate ({})?'.format(fname2)
            return 

    doc = collections.defaultdict(str)
    cmd = ['pdftotext', '-enc', 'ASCII7', fname, '-']
    doc['fulltext'] = Popen(cmd, stdout=PIPE).communicate()[0]
    doc['bibtex'] = fetch_bibtex(extract_title(fname))
    doc.update(parse_bibtex(doc['bibtex']))
    
    with con:
        con.execute('INSERT INTO fts (fulltext) VALUES (?)', 
            (doc['fulltext'],))
        cur = con.execute('INSERT INTO documents DEFAULT VALUES')
    doc['rowid'] = cur.lastrowid
    doc['filename'] = fname
    doc['filename'] = get_filename(doc)
    shutil.copy(fname, os.path.join(DOCUMENT_DIR, doc['filename']))
    update_document(doc)
    return doc['rowid']


def delete_document(rowid):
    doc = next(select_documents(('rowid', 'filename'), (rowid,)))
    with con:
        con.execute('DELETE FROM documents WHERE rowid=?', (doc['rowid'],))
        con.execute('DELETE FROM fts WHERE rowid=?', (doc['rowid'],))
    os.remove(os.path.join(DOCUMENT_DIR, doc['filename']))


def get_filename(doc):
    if doc['author'].count(', ') > 2:
        author = doc['author'].split(', ')[0] + ' et al.'
    else:
        author = doc['author']
    fields = (author, doc['year'], doc['title'], str(doc['rowid'])) 
    filename = ' - '.join(re.sub(r'[^-\w, ]', '', f) for f in fields if f)
    filename += '.' + doc['filename'].split('.')[-1]
    return filename


def check_filenames():
    filenames = set(os.listdir(DOCUMENT_DIR))
    for row in con.execute('SELECT filename FROM documents'):
        if row['filename'] not in filenames:
            raise IOError('Filename not found ' + row['filename'])
        filenames.remove(row['filename'])
    for filename in filenames:
        raise IOError('Filename not in database ' + filename)


def parse_bibtex(bibtex):
    d = collections.defaultdict(str)
    reg = r'^\s*(title|author|year|journal)={*(.+?)}*,?$'
    d.update(dict(re.findall(reg, bibtex, re.MULTILINE)))
    for k, v in d.items():
        d[k] = re.sub('[^-\w ,:]', '', v)
    d['author'] = ', '.join(a[:a.find(',')]
        for a in d['author'].split(' and '))
    return d


def get_tags():
    tags = set()
    for row in con.execute('SELECT DISTINCT tags FROM documents'):
        tags.update(map(str.strip, row['tags'].split(';')))
    return tags


def extract_title(fname):
    cmd = ['pdftohtml', '-enc', 'ASCII7', '-xml', '-stdout', '-l', '2', fname]
    xml = Popen(cmd, stdout=PIPE).communicate()[0]

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
    url = '/scholar?q=allintitle:' + urllib2.quote(title)
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


@delay(8, 10)
def scholar_read(url):
    id = ''.join(random.choice('0123456789abcdef') for i in range(16))
    cookie = 'GSP=ID={}:CF=4;'.format(id)
    h = {'User-agent': 'Mozilla/5.0', 'Cookie': cookie}
    req = urllib2.Request('http://scholar.google.com' + url, headers=h)
    return unescape(urllib2.urlopen(req).read().decode('utf8').encode('utf8'))


def striptags(html):
    return re.sub(r'<[^>]+>', '', html)


def unescape_charref(ref):
    name = ref[2:-1]
    base = 10
    if name.startswith("x"):
        name = name[1:]
        base = 16
    return unichr(int(name, base)).encode('utf8')


def replace_entities(match):
    ent = match.group()
    if ent[1] == "#":
        return unescape_charref(ent)

    repl = htmlentitydefs.name2codepoint.get(ent[1:-1])
    if repl is not None:
        repl = unichr(repl).encode('utf8')
    else:
        repl = ent
    return repl


def unescape(data):
    return re.sub(r"&#?[A-Za-z0-9]+?;", replace_entities, data)


for dir in (BASE_DIR, DOCUMENT_DIR):
    if not os.path.exists(dir):
        os.mkdir(dir)
 
con = sqlite3.connect(os.path.join(BASE_DIR, 'documents.sqlite3'))
con.row_factory = sqlite3.Row
con.text_factory = str
con.execute("ATTACH '{}' as fts".format(os.path.join(BASE_DIR, 'fts.sqlite3')))

fts_columns = 'title', 'author', 'journal', 'tags', 'notes', 'fulltext'
create_tables()

if __name__ == '__main__':
    pass
    import_mendeley()
    #create_test_data()
    optimize()
