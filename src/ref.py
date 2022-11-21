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


import subprocess
import collections
import filecmp
from html import unescape
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
import urllib.request, urllib.error, urllib.parse
import json


documents_fields = (
    ('docid', 'INTEGER PRIMARY KEY'), ('tags', 'TEXT'), ('title', 'TEXT'),
    ('author', 'TEXT'), ('year', 'INTEGER'), ('rating', 'INTEGER'),
    ('journal', 'TEXT'), ('filename', 'TEXT'), ('notes', 'TEXT'),
    ('bibtex', 'TEXT')
)

cfg = {
    'base_dir'   : '~/.ref',
    'Cookie'     : 'GSP=ID={}:CF=4;'.format(''.join(random.choice('0123456789abcdef') for i in range(16))),
    'User-Agent' : 'Mozilla/5.0'
}

def import_folder(foldername, recurse=True, del_files=False):
    print("Import folder {}".format(foldername))
    for f in sorted(os.listdir(foldername), key=os.path.getmtime):
        print(f)
        if os.path.isdir(os.path.join(foldername,f)):
            if recurse:
                import_folder(os.path.join(foldername,f), recurse, del_files)
        if os.path.splitext(f)[1].lower() not in extract_funs:
            #print 'not in extract_funs', os.path.splitext(f)[1].lower(), extract_funs.keys()
            continue
        try:
            fname = os.path.join(foldername, f)
            print(fname)
            insert_document(fname)
            if del_files:
                os.remove(fname)
        except DuplicateError:
            print('Skipping duplicate ', f)
        except Exception as e:
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
    if ext.lower() not in extract_funs:
        raise ValueError('Unsupported file type {}'.format(ext.lower()))

    doc = collections.defaultdict(str)
    title, doc['fulltext'], arxivId = extract_funs[ext.lower()](fname)
    doc['title'] = title[:127]
    doc['rating'] = 'U'
    # default dummy bibtex with title and arxivId
    doc['bibtex'] = dummy_bibtex(doc['title'], arxivId)

    if fetch:
        try:
            newbibtex   = fetch_bibtex(doc['title'], arxivId)
            newbibtex_p = parse_bibtex(newbibtex)
            if arxivId or approximate_match(newbibtex_p['title'], doc['title']):
                # trust new bibtex based on title matching (scholar) or retrieving on arxivId.
                doc['bibtex'] = newbibtex
                doc.update(newbibtex_p)
            else:
                raise ValueError('Retrieved a non-matching bibtex. Correct and :Fetch', newbibtex)
        except (urllib.error.HTTPError, urllib.error.URLError, AttributeError, AssertionError, ValueError) as e:
            #pass # ref functions are quiet, fetch can silently fail with known errors
            print(e)
            print('bibtex fetch failed, continue with default bibtex')
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
    for k, v in list(d.items()):
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
    cmd = ['djvutxt', fname]
    fulltext = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    title = re.match(r'(.*?)\n\n', fulltext, re.DOTALL).group(0)
    title = re.sub(r'\s+', ' ', title).strip()
    if len(title) > 100:
        title = ''
    return title, fulltext, None


def extract_pdf(fname):
    cmd = ['pdftotext', '-enc', 'ASCII7', fname, '-']
    fulltext = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout

    cmd = ['pdftohtml', '-enc', 'ASCII7', '-xml', '-stdout', '-l', '3', '-i', fname]
    xml = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout

    title, arxivId = extract_heuristic(fname, fulltext, xml)
    return title, fulltext, arxivId

# MODULE GLOBAL DICT
extract_funs = {'.pdf': extract_pdf, '.djvu': extract_djvu}

def parse_arxiv(s, prefix=True, version=True):
    pattern = (r'arXiv:' if prefix else '') + r'(\d{4}).(\d{5})' + (r'v(\d)' if version else '')
    #res = re.findall(r'arXiv:(\d{4}).(\d{5})v(\d)', s) if full else re.findall(r'(\d{4}).(\d{5})',s)
    res = re.findall(pattern, s)
    return '{0}.{1}'.format(*res[0]) if len(res)==1 else None

def extract_heuristic(fname, fulltext, xml):
    ### arxiv: extract Id (discard version); appearing in fname and beginning of fulltext.
    arxivId = parse_arxiv(fname, False, False)
    arxivId = arxivId if arxivId else parse_arxiv(fulltext[:200], True, True) 

    title = title_heuristic_fontsize(xml)
    if 'ICLR' in fulltext.split('\n')[0] and len(title) < 12: # no decent title expected
        title = title_heuristic_iclr(fulltext)
    return title, arxivId

def title_heuristic_fontsize(xml):
    ### Fontsize heuristic for the title
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
        title = ' '.join([xs[2] for xs in group]).strip()
        if 'arxiv' in title.lower():
            continue
        bad = ('abstract', 'introduction', 'relatedwork', 'originalpaper', 'bioinformatics')
        if len(title) >= 5 and re.sub(r'[\d\s]', '', title).lower() not in bad:
            break
    return title

def title_heuristic_iclr(fulltext):
    lines = fulltext.split('\n')
    try:
        assert lines[1].strip() == ''
        title = []
        for line in lines[2:]:
            if not line.isupper():
                break
            #chopped_words = re.findall(r'[^\w](\w) (\w+)', line)
            chopped_words = re.findall(r'(?:[^\w]|^)(\w|\')?(?: |^|-)(\w+)', line)
            title += [a+b for a,b in chopped_words]
        return ' '.join(title)
    except: # catchall
        return ''

def approximate_match(tnew, told):
    if tnew == told:
        return True
    tnew, told = (re.sub('[^\w ]','',s.lower()).split() for s in (tnew, told))
    if tnew == told:
        return True
    tnew, told = ([w for w in t if meaningful(w)] for t in (tnew, told))
    if tnew == told or set(tnew) == set(told):
        return True
    elif len(set(tnew) - set(told)) < 0.3 * len(set(told)):
        return True
    # hmm maybe better just do edit distance.. this may fail for short titles
    return False

def meaningful(word):
    return len(word) > 3 or word=='gan'

def dummy_bibtex(title, arxivId):
    bibtex = ['@article{defaultbib,',
              '  title={{{}}},'.format(title),
              '}', '']
    if arxivId:
        bibtex.insert(-2, '  journal ={{arXiv:{}}},'.format(arxivId))
        bibtex.insert(-2, '  year    ={{{}}},'.format(2000+int(arxivId[:2])))
        bibtex.insert(-2, '  eprint  ={{{}}},'.format(arxivId))
    return '\n'.join(bibtex)

def fetch_bibtex(title, arxivId):
    # Raises urllib2 errors
    if arxivId:
        bibtex = fetch_bibtex_arxiv(arxivId)
    else:
        bibtex = fetch_bibtex_gscholar(title)
    bibtex  = bibtex.replace('arXiv preprint arXiv:', 'arXiv:') # in field 'journal'
    arxivId = arxivId if arxivId else parse_arxiv(bibtex, True, False)
    # Make sure arxivId is added as field eprint, https://arxiv.org/hypertex/bibstyles/
    if arxivId and 'eprint' not in parse_bibtex(bibtex):
        lines = bibtex.strip().split('\n')
        lines[-2] += ',' if not lines[-2].strip()[-1]==',' else '' # end with comma
        lines.insert(-1, '  archivePrefix={arXiv},')
        lines.insert(-1, '  eprint       ={{{}}},'.format(arxivId))
        bibtex = '\n'.join(lines + [''])
    return bibtex

def fetch_bibtex_gscholar(title):
    # Raises urllib2 errors, ValueError
    url = '/scholar?q=allintitle:' + urllib.parse.quote(title)
    return scholar_query(url)

def fetch_bibtex_arxiv(arxivId, timeout=2.0):
    # Raises urllib2 errors, ValueError
    # TODO explore arxiv auto bibtex or just generate from arXiv/abs page?
    # google scholar has delay of couple days..
    # https://tex.stackexchange.com/questions/3833/how-to-cite-an-article-from-arxiv-using-bibtex
    # For now just go back to scholar but with arxivId..
    #url = '/scholar?q=' + urllib2.quote('source:'+arxivId)
    url = '/scholar?q=source:'+arxivId
    return scholar_query(url)

def scholar_query(url):
    query_response = scholar_read(url)
    match = re.search(r'<a href="[^"]*(/scholar.bib[^"]+)', query_response)
    if match:
        return scholar_read(match.group(1))
    else:
        raise  ValueError('No bibtex found on google scholar (cookie correct? bot-blocked?)')

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


@delay(2, 1)
def scholar_read(url, timeout=2.0):
    h         = {'User-Agent': cfg['User-Agent'], 'Cookie': cfg['Cookie']}
    req = urllib.request.Request('http://scholar.google.com' + url, headers=h)
    return unescape(urllib.request.urlopen(req, timeout=timeout).read().decode('utf8'))

def striptags(html):
    return unescape(re.sub(r'<[^>]+>', '', html))


def export_bib(fname):
    rows = con.execute('SELECT bibtex FROM documents')
    open(fname, 'w').write('\n\n'.join(row['bibtex'] for row in rows))


def init(override_basedir=None):
    global cfg, con, BASE_DIR, DOCUMENT_DIR

    try:
        with open(os.path.expanduser('~/.ref.conf')) as fh:
            cfgLoaded = json.loads(fh.read())
        cfg = {k: cfgLoaded[k] if k in cfgLoaded else cfg[k] for k,v in list(cfg.items())}
    except IOError as e:
        pass # config file not mandatory
    except ValueError as e:
        print(("~/.ref.conf contains an error: %s" % str(e)))

    if override_basedir:
        BASE_DIR = override_basedir
    else:
        BASE_DIR = os.path.expanduser(cfg['base_dir'])
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


def main():
    init()
    print(scholar_query('/scholar?q=source:2206.14486'))

if __name__ == "__main__":
    main()
