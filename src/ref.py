# The MIT License (MIT)
#
# Copyright (c) 2014, Jure Zbontar <jure.zbontar@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


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
import HTMLParser


documents_fields = (
    ('docid', 'INTEGER PRIMARY KEY'), ('tags', 'TEXT'), ('title', 'TEXT'),
    ('author', 'TEXT'), ('year', 'INTEGER'), ('rating', 'INTEGER'),
    ('journal', 'TEXT'), ('filename', 'TEXT'), ('notes', 'TEXT'),
    ('bibtex', 'TEXT')
)

def import_dir(dir,recursive=True):
    for base in os.listdir(dir):
        try:
            print base
            if os.path.isdir(os.path.join(dir,base)):
                if recursive:
                    print "Enter Folder {}".format(base)
                    import_dir(os.path.join(dir,base),True)
                    print "Exit Folder {}".format(base)
                else:
                    print " -- skip directory"
            else:
                insert_document(os.path.join(dir, base))
        except DuplicateError:
            print 'Skipping duplicate ',base
        except Exception as e:
            #print e
            #print 'Skipping', base
            raise

def check_filenames():
    filenames = set(os.listdir(DOCUMENT_DIR))
    for row in con.execute('SELECT filename FROM documents'):
        if row['filename'] not in filenames:
            raise IOError('Filename not found ' + row['filename'])
        filenames.remove(row['filename'])
    for filename in filenames:
        raise IOError('Filename not in database ' + filename)


def create_tables():
    c = con.execute("SELECT rowid FROM sqlite_master WHERE type='table'")
    if len(c.fetchall()) == 0:
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
    if doc['filename'] != filename:
        src = os.path.join(DOCUMENT_DIR, doc['filename'])
        dst = os.path.join(DOCUMENT_DIR, filename)
        os.rename(src, dst)
        doc['filename'] = filename

    fs = ','.join(name + '=?' for name, _ in documents_fields[1:])
    vs = [doc[name] for name, _ in documents_fields[1:]] + [doc['docid']]
    try:
        con.execute('SAVEPOINT update_document')
        con.execute('UPDATE documents SET {} WHERE docid=?'.format(fs), vs)
        con.execute('RELEASE SAVEPOINT update_document')
    except:
        con.execute('ROLLBACK TO update_document')
        raise

class DuplicateError(Exception):
    pass

def insert_document(fname, fetch=True):
    if not os.path.isfile(fname):
        raise IOError('{} is not a file'.format(fname))

    for base2 in os.listdir(DOCUMENT_DIR):
        fname2 = os.path.join(DOCUMENT_DIR, base2)
        if filecmp.cmp(fname, fname2):
            raise DuplicateError(base2)

    ext = os.path.splitext(fname)[1]
    extract_funs = {'.pdf': extract_pdf, '.chm': extract_chm, '.djvu': extract_djvu}
    if ext not in extract_funs:
        raise ValueError('Unsupported file type {}'.format(ext))

    doc = collections.defaultdict(str)
    title, doc['fulltext'] = extract_funs[ext](fname)
    doc['title'] = title[:127]
    doc['rating'] = 'U'
    if fetch:
        if len(title)>0:
            doc['bibtex'] = fetch_bibtex(doc['title'])
            if not doc['bibtex']:
                doc['bibtex'] = '@{{\n  title={}\n}}\n'.format(doc['title'])
            doc.update(parse_bibtex(doc['bibtex']))
            doc['title'] = title[:127]
        else:
            # no title found
            doc['bibtex'] = '@{{\n  title=\n}}\n'

    try:
        con.execute('SAVEPOINT insert_document')
        ft_c = con.execute('INSERT INTO fulltext VALUES (?)', (doc['fulltext'],))
        c = con.execute('INSERT INTO documents DEFAULT VALUES')
        assert c.lastrowid == ft_c.lastrowid

        doc['docid'] = c.lastrowid
        doc['filename'] = fname  # setup arguments for get_filename
        doc['filename'] = get_filename(doc)
        update_document(doc)
        shutil.copy(fname, os.path.join(DOCUMENT_DIR, doc['filename']))
        con.execute('RELEASE SAVEPOINT insert_document')
    except:
        con.execute('ROLLBACK TO insert_document')
        raise

    return doc['docid']


def delete_document(docid):
    doc = next(select_documents(('docid', 'filename'), (docid,)))
    try:
        con.execute('BEGIN')
        con.execute('DELETE FROM documents WHERE docid=?', (doc['docid'],))
        con.execute('DELETE FROM fulltext WHERE docid=?', (doc['docid'],))
        os.remove(os.path.join(DOCUMENT_DIR, doc['filename']))
        con.execute('COMMIT')
    except:
        con.execute('ROLLBACK')
        raise


def search_documents(fields, query, order='docid DESC'):
    res = []
    for field in ('tags', 'title', 'author', 'journal', 'notes'):
        cur = con.execute('''SELECT {} FROM documents WHERE {} LIKE ?
            ORDER BY {}'''.format(','.join(fields), field, order),
            ('%' + query + '%',))
        res.append((field, cur))
    cur = con.execute('''SELECT {} FROM documents JOIN
        (SELECT docid FROM fulltext WHERE content MATCH ?)
        USING(docid) ORDER BY {}'''.format(','.join(fields), order), (query,))
    res.append(('fulltext', cur))
    return res


def get_filename(doc):
    if doc['author'].count(', ') > 2:
        author = doc['author'].split(', ')[0] + ' et al'
    else:
        author = doc['author']
    fields = (author, doc['year'], doc['title'], doc['docid'])
    filename = ' - '.join(re.sub(r'[^-\w,. ]', '', str(f)) for f in fields if f)
    filename += os.path.splitext(doc['filename'])[1]
    return filename


def parse_bibtex(bibtex):
    d = collections.defaultdict(str)
    reg = r'^\s*(\w+)\s*=\s*{*(.+?)}*,?$'
    d.update(dict(re.findall(reg, bibtex, re.MULTILINE)))
    for k, v in d.items():
        d[k] = re.sub(r'[\'"{}\\=]', '', v)
    d['author'] = ', '.join(a.split(',')[0] for a in d['author'].split(' and '))
    if 'journal' not in d:
        d['journal'] = d.get('booktitle', '')
    return d


def get_tags():
    tags = set()
    for row in con.execute('SELECT tags FROM documents'):
        tags.update(tag for tag in row['tags'].split(';') if tag)
    return tags


def extract_djvu(fname):
    fulltext = Popen(['djvutxt', fname], stdout=PIPE).communicate()[0]
    title = re.match(r'(.*?)\n\n', fulltext, re.DOTALL).group(0)
    title = re.sub(r'\s+', ' ', title).strip()
    if len(title) > 100:
        title = ''
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

    title = ''
    for _, group in sorted(groups, key=lambda xs: xs[0], reverse=True):
        title = ' '.join(map(lambda xs: xs[2], group)).strip()
        if 'arxiv' in title.lower():
            continue
        bad = ('abstract', 'introduction', 'relatedwork', 'originalpaper', 'bioinformatics')
        if len(title) >= 5 and re.sub(r'[\d\s]', '', title).lower() not in bad:
            break
    return title, fulltext


def fetch_bibtex(title):
    try:
        url = '/scholar?q=allintitle:' + urllib2.quote(title)
        match = re.search(r'<a href="(/scholar.bib[^"]+)', scholar_read(url))
        return scholar_read(match.group(1))
    except (urllib2.HTTPError, urllib2.URLError, AttributeError):
        return


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


@delay(2, 3)
def scholar_read(url):
    id = ''.join(random.choice('0123456789abcdef') for i in range(16))
    cookie = 'GSP=ID={}:CF=4;'.format(id)
    h = {'User-agent': 'Mozilla/5.0', 'Cookie': cookie}
    req = urllib2.Request('http://scholar.google.com' + url, headers=h)
    return unescape(urllib2.urlopen(req).read().decode('utf8')).encode('utf8')


def striptags(html):
    return unescape(re.sub(r'<[^>]+>', '', html))


unescape = HTMLParser.HTMLParser().unescape


def export_bib(fname):
    rows = con.execute('SELECT bibtex FROM documents')
    open(fname, 'w').write('\n\n'.join(row['bibtex'] for row in rows))


def init(base_dir=os.path.expanduser('~/.ref')):
    global con, BASE_DIR, DOCUMENT_DIR

    BASE_DIR = base_dir
    DOCUMENT_DIR = os.path.join(BASE_DIR, 'documents')

    for dir in (BASE_DIR, DOCUMENT_DIR):
        if not os.path.exists(dir):
            os.mkdir(dir)

    con = sqlite3.connect(os.path.join(BASE_DIR, 'documents.sqlite3'))
    con.isolation_level = None
    con.row_factory = sqlite3.Row
    con.text_factory = str
    con.execute("ATTACH '{}' as fulltext".format(os.path.join(BASE_DIR, 'fulltext.sqlite3')))
    create_tables()
