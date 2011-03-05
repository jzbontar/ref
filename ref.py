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
import tempfile
import time
import urllib2


BASE_DIR = os.path.expanduser('~/.ref/')
DOCUMENT_DIR = os.path.join(BASE_DIR, 'documents/')


def import_dir(dir):
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
            elif q < 0.8:
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
            
            c = con.execute('INSERT INTO fulltext VALUES (?)', (fulltext,))
            lastrowid = c.lastrowid
            c = con.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)',
                (None, tags, title, author, year, rating, journal, filename, 
                notes, bibtex))
            assert lastrowid == c.lastrowid



def create_tables():
    with con:
        c = con.execute("SELECT rowid FROM sqlite_master WHERE type='table'")
        if len(c.fetchall()) > 0:
            return
        fields = ','.join(name + ' ' + type for name, type in documents_fields)
        con.execute('CREATE TABLE documents ({})'.format(fields))
        con.execute('CREATE VIRTUAL TABLE fulltext.fulltext USING fts4')


def select_documents(fields, docids=None, order='docid DESC'):
    sql = 'SELECT {} FROM documents'.format(','.join(fields))
    if docids:
       sql += ' WHERE docid in ({})'.format(','.join(map(str, docids)))
    sql += ' ORDER BY ' + order
    return con.execute(sql)


def update_document(doc):
    filename = get_filename(doc)
    if False and doc['filename'] != filename:
        src = os.path.join(DOCUMENT_DIR, doc['filename'])
        dst = os.path.join(DOCUMENT_DIR, filename)
        os.rename(src, dst)
        doc['filename'] = filename

    fs = ','.join(name + '=?' for name, _ in documents_fields[1:])
    vs = [doc[name] for name, _ in documents_fields[1:]] + [doc['docid']]
    with con:
        con.execute('UPDATE documents SET {} WHERE docid=?'.format(fs), vs)
        
    
def insert_document(fname):
    cleanup = []
    if os.path.splitext(fname)[1] == '.7z':
        fname, cleanup_func = extract_7z(fname)
        cleanup.append(cleanup_func)

    for base2 in os.listdir(DOCUMENT_DIR):
        fname2 = os.path.join(DOCUMENT_DIR, base2)
        if filecmp.cmp(fname, fname2):
            print 'Duplicate ({})?'.format(fname2)
            return 

    ext = os.path.splitext(fname)[1]
    fs = {'.pdf': extract_pdf, '.chm': extract_chm, '.djvu': extract_djvu}
    extract_func = fs.get(ext, lambda fname: (None, None))

    doc = collections.defaultdict(str)
    doc['title'], doc['fulltext'] = extract_func(fname)
    doc['bibtex'] = fetch_bibtex(doc['title'])
    doc.update(parse_bibtex(doc['bibtex']))
    
    with con:
        c = con.execute('INSERT INTO fulltext VALUES (?)', (doc['fulltext'],))
        lastrowid = c.lastrowid
        c = con.execute('INSERT INTO documents DEFAULT VALUES')
        assert c.lastrowid == lastrowid
    doc['docid'] = c.lastrowid
    doc['filename'] = fname
    doc['filename'] = get_filename(doc)
    shutil.copy(fname, os.path.join(DOCUMENT_DIR, doc['filename']))
    update_document(doc)
    for cleanup_func in cleanup:
        cleanup_func()
    return doc['docid']


def delete_document(docid):
    doc = next(select_documents(('docid', 'filename'), (docid,)))
    with con:
        con.execute('DELETE FROM documents WHERE docid=?', (doc['docid'],))
        con.execute('DELETE FROM fts WHERE docid=?', (doc['docid'],))
        os.remove(os.path.join(DOCUMENT_DIR, doc['filename']))


def search_documents(fields, query):
    res = []
    for field in ('tags', 'title', 'author', 'journal', 'notes'):
        cur = con.execute('SELECT {} FROM documents WHERE {} LIKE ?'.format(
            ','.join(fields), field), ('%' + query + '%',))
        res.append((field, cur))
    cur = con.execute('''SELECT {} FROM documents JOIN 
        (SELECT docid FROM fulltext WHERE content MATCH ?)
        USING(docid)'''.format(','.join(fields)), (query,))
    res.append(('fulltext', cur))
    return res
        

def get_filename(doc):
    if doc['author'].count(', ') > 2:
        author = doc['author'].split(', ')[0] + ' et al.'
    else:
        author = doc['author']
    fields = (author, doc['year'], doc['title'], str(doc['docid'])) 
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
        d[k] = re.sub(r'[{}\\=]', '', v)
    d['author'] = ', '.join(a[:a.find(',')]
        for a in d['author'].split(' and '))
    return d


def get_tags():
    tags = set()
    for row in con.execute('SELECT tags FROM documents'):
        tags.update(map(str.strip, row['tags'].split(';')))
    return tags


def extract_7z(fname):
    def cleanup():
        shutil.rmtree(dir)

    name = os.path.splitext(os.path.basename(fname))[0]
    dir = tempfile.mkdtemp(prefix='ref.')
    for pwd in ('ebooksclub.org', 'ebooksclub_org', 'gigapedia.com', 'library.nu'):
        p = Popen(['7z', 'x', fname, '-y', '-p' + pwd, '-o' + dir], stdout=PIPE)
        p.communicate()
        if p.returncode == 0:
            for base in os.listdir(dir):
                if os.path.splitext(base)[0] == name:
                    return os.path.join(dir, base), cleanup
    raise Exception('Could not extract 7z file.')


def extract_djvu(fname):
    fulltext = Popen(['djvutxt', fname], stdout=PIPE).communicate()[0]
    title = re.match(r'(.*?)\n\n', fulltext, re.DOTALL).group(0)
    title = re.sub(r'\s+', ' ', title).strip()
    if len(title) > 100:
        title = None
    return title, fulltext


def extract_chm(fname):
    dir = tempfile.mkdtemp(prefix='ref.')
    Popen(['extract_chmLib', fname, dir], stdout=PIPE).communicate()
    for base in os.listdir(dir):
        name, ext = os.path.splitext(base)
        if ext == '.hhc':
            hhc = open(os.path.join(dir, base)).read()
            title = re.search(r'name="Name" value="([^"]+)"', hhc).group(1)
            fulltext = ''
            for html in re.findall(r'"({}/[^"]+)"'.format(name), hhc):
                fulltext += striptags(open(os.path.join(dir, html)).read())
            break
    shutil.rmtree(dir)
    return title, fulltext
        

def extract_pdf(fname):
    cmd = ['pdftotext', '-enc', 'ASCII7', fname, '-']
    fulltext = Popen(cmd, stdout=PIPE).communicate()[0]

    cmd = ['pdftohtml', '-enc', 'ASCII7', '-xml', '-stdout', '-l', '3', fname]
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

    title = None
    for _, group in sorted(groups, key=lambda xs: xs[0], reverse=True):
        title = ' '.join(map(lambda xs: xs[2], group)).strip()
        bad = ('abstract', 'introduction', 'relatedwork', 'originalpaper', 'bioinformatics')
        if len(title) >= 5 and re.sub(r'[\d\s]', '', title).lower() not in bad:
            break
    return title, fulltext


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


@delay(2, 2)
def scholar_read(url):
    id = ''.join(random.choice('0123456789abcdef') for i in range(16))
    cookie = 'GSP=ID={}:CF=4;'.format(id)
    h = {'User-agent': 'Mozilla/5.0', 'Cookie': cookie}
    req = urllib2.Request('http://scholar.google.com' + url, headers=h)
    return unescape(urllib2.urlopen(req).read().decode('utf8').encode('utf8'))


def striptags(html):
    return unescape(re.sub(r'<[^>]+>', '', html))


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

documents_fields = (
    ('docid', 'INTEGER PRIMARY KEY'), ('tags', 'TEXT'), ('title', 'TEXT'), 
    ('author', 'TEXT'), ('year', 'INTEGER'), ('rating', 'INTEGER'), 
    ('journal', 'TEXT'), ('filename', 'TEXT'), ('notes', 'TEXT'), 
    ('bibtex', 'TEXT')
)
 
con = sqlite3.connect(os.path.join(BASE_DIR, 'documents.sqlite3'))
con.row_factory = sqlite3.Row
con.text_factory = str
con.execute("ATTACH '{}' as fulltext".format(os.path.join(BASE_DIR, 'fulltext.sqlite3')))

create_tables()

if __name__ == '__main__':
    pass
    #extract_chm('/home/jure/tmp/uM7TZdWNFGIk.chm')
    import_dir('/home/jure/.ref.old/documents')
    #create_test_data()
