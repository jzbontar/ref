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
import sys
import time
import urllib2


BASE_DIR = os.path.expanduser('~/.library/')
DOCUMENT_DIR = os.path.join(BASE_DIR, 'documents/')


def create_tables():
    cur.execute('DROP TABLE IF EXISTS documents')
    cur.execute('''CREATE TABLE documents 
        (bibtex TEXT, author TEXT, title TEXT, year INTEGER, rating INTEGER, 
        filename TEXT, fulltext TEXT)''')
    cur.execute('DROP TABLE IF EXISTS tags')
    cur.execute('CREATE TABLE tags (name TEXT)')
    cur.execute('DROP TABLE IF EXISTS documents_tags')
    cur.execute('CREATE TABLE documents_tags (document INTEGER, tag INTEGER)')


def select_documents(id=None):
    args = []
    where = ''
    if id:
        where = ' WHERE rowid=?'
        args.append(id)
    cur.execute('''SELECT rowid, bibtex, author, title, year, rating, filename
        FROM documents''' + where, args)
    return [dict(row) for row in cur]


def update_document(doc):
    b = parse_bibtex(doc['bibtex'])
    cur.execute('''UPDATE documents SET 
        bibtex=?, author=?, title=?, year=?, rating=?,filename=?
        WHERE rowid=?''',
        (doc['bibtex'], b['author'], b['title'], b['year'], doc['rating'], 
        doc['filename'], doc['rowid']))
        
    
def insert_document(fname):
    if os.path.splitext(fname)[1] != '.pdf':
        return
    for fname2 in os.listdir(DOCUMENT_DIR):
        if filecmp.cmp(fname, os.path.join(DOCUMENT_DIR, fname2)):
            return 

    base = os.path.basename(fname)
    cmd = ['pdftotext', fname, '-']
    fulltext = Popen(cmd, stdout=PIPE).communicate()[0].decode('utf8')
    title = extract_title(fname)
    bibtex = fetch_bibtex(title)
    b = parse_bibtex(bibtex)
    print('+ ' + b['title'])
    
    cur.execute('''INSERT INTO documents
        (bibtex, author, title, year, filename, fulltext) VALUES
        (?, ?, ?, ?, ?, ?)''', 
        (bibtex, b['author'], b['title'], b['year'], base, fulltext))

    shutil.copy(fname, os.path.join(DOCUMENT_DIR, base))
    return cur.lastrowid


def import_mendeley():
    dir = u'/home/jure/.mendeley'
    for base in os.listdir(dir):
        add_document(os.path.join(dir, base))
    

def parse_bibtex(bibtex):
    d = collections.defaultdict(unicode)
    reg = r'^\s*(title|author|year)={*(.+?)}*,?$'
    d.update(dict(re.findall(reg, bibtex, re.MULTILINE)))
    return d


def extract_title(fname):
    cmd = ['pdftohtml', '-xml', '-stdout', '-l', '1', fname]
    xml = Popen(cmd, stdout=PIPE).communicate()[0].decode('utf8')

    # pdftohtml has trouble with the letters 'fi'
    xml = xml.replace(unichr(64257), 'fi')

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


def scholar_read(url):
    time.sleep(1)
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


conn = sqlite3.connect(os.path.join(BASE_DIR, 'db.sqlite3'))
conn.isolation_level = None
conn.row_factory = sqlite3.Row
cur = conn.cursor()

for dir in (BASE_DIR, DOCUMENT_DIR):
    if not os.path.exists(dir):
        os.mkdir(dir)

#create_tables()
#import_mendeley()
