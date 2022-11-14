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
import os
import platform
import glob
import re
import sqlite3
import sys
import vim
import collections
import urllib.request, urllib.parse, urllib.error, urllib.request, urllib.error, urllib.parse

import ref

XDG_OPEN = ['xdg-open', 'open'][platform.system()=="Darwin"]

def search_documents(query):
    global last_select_cmd

    if not query:
        reload_main()
        return

    last_select_cmd = lambda: search_documents(query)
    del main_buf[:]
    for field, docs in ref.search_documents(headers, query, order):
        docs = list(map(str_document, docs))
        if docs:
            heading = '# {}'.format(field.upper())
            if len(main_buf) == 1:
                main_buf[:] = [heading]
            else:
                main_buf.append('')
                main_buf.append(heading)
            main_buf[len(main_buf):] = docs


def parse_info():
    bibtex, rest, notes = '\n'.join(info_buf).split('\n---')
    doc = ref.parse_bibtex(bibtex)
    doc.update(dict(re.findall(r'(\w+)=(.*)', rest)))
    doc['bibtex'] = bibtex
    doc['docid'] = int(doc['docid'])
    doc['notes'] = notes.strip()
    doc.update(next(ref.select_documents(('filename',), (doc['docid'],))))
    tags.update(doc['tags'].split('; '))
    return doc


def write_info(doc):
    if not doc:
        info_buf[:] = []
        return
    buf = (doc['bibtex'] or '').splitlines()
    if not buf:
        buf = ['@{', '  title=' + (doc['title'] or ''), '}']
    buf.append('---')
    for attr in ('docid', 'tags', 'rating'):
        buf.append('{}={}'.format(attr, doc[attr] or ''))
    buf.append('---')
    buf.extend(doc['notes'].splitlines())
    info_buf[:] = buf


def save_info(doc):
    ref.update_document(doc)
    update_main((doc['docid'],))


def get_docid(line):
    try:
        return int(line.split()[0])
    except (ValueError, IndexError):
        return None


def str_document(doc):
    s = '  '.join(
        str(doc[h] or '')[:col_size[h]].ljust(col_size[h])
         for h in headers
    )
    return s


def selected_document():
    docid = get_docid(main_buf[main_win.cursor[0] - 1])
    if docid:
        fields = headers + ('bibtex', 'tags', 'filename', 'notes')
        docs = list(ref.select_documents(fields, (docid,)))
        if docs:
            return docs[0]


def resize():
    global col_size

    info_win.height = 15
    col_size = {'year': 4, 'docid': 5, 'rating': 2, 'author': 30}
    col_size['title'] = main_win.width - sum(col_size.values()) - 2 * len(col_size)

    update_main()


def update_main(docids=None):
    if not docids:
        docids = [_f for _f in (get_docid(line) for line in main_buf) if _f]
        if not docids:
            return
    cur = ref.select_documents(headers, docids)
    docs = {doc['docid']: str_document(doc) for doc in cur}

    for i, line in enumerate(main_buf):
        id = get_docid(line)
        if id in docs:
            main_buf[i] = docs[id]


def reload_main():
    global last_select_cmd

    last_select_cmd = reload_main
    docs = list(map(str_document, ref.select_documents(headers, order=order)))
    main_buf[:] = docs


def fetch_bibtex():
    doc = parse_info()
    try:
        doc['bibtex'] = ref.fetch_bibtex(doc['title'], arxivId=None)
        # TODO also consider arXiv fetching here? This will always go to gscholar..
        # I probably want a new column in the dbase "eprint"= arXiv:XX | openreview:xxx
        # see https://arxiv.org/hypertex/bibstyles/
    except (urllib.error.HTTPError, urllib.error.URLError, AttributeError) as e:
        print('Fetch failed: %s' % str(e))
        return
    doc.update(ref.parse_bibtex(doc['bibtex']))
    save_info(doc)
    write_info(doc)


def open_document():
    filename = selected_document()['filename']
    Popen([XDG_OPEN, os.path.join(ref.DOCUMENT_DIR, filename)], stderr=PIPE, stdout=PIPE)


def add_document(fname):
    docid = ref.insert_document(fname)
    if docid:
        doc = next(ref.select_documents(headers, (docid,)))
        main_buf[:0] = [str_document(doc)]
    main_win.cursor = (1, 0)

def add_document_del(fname):
    add_document(fname) # copies pdf over to ref.DOCUMENT_DIR
    os.remove(fname)

def add_folder(fname):
    ref.import_folder(fname, recurse=True, del_files=False)
    reload_main()

def add_folder_del(fname):
    ref.import_folder(fname, recurse=True, del_files=True)
    reload_main()

def add_arxiv(url_or_id):
    arxivId = ref.parse_arxiv(url_or_id, False, False) # can be just id, or filename, or html/pdf url.
    pdfUrl  = 'https://arxiv.org/pdf/{}.pdf'.format(arxivId)
    fname   ='ref.tmp.{}.pdf'.format(arxivId)
    urllib.request.urlretrieve(pdfUrl, fname)
    add_document_del(fname)

def export_bib(fname):
    ref.export_bib(fname)

def delete_document(lineFrom, lineTo):
    if vim.current.buffer != main_buf:
        print('Deletion is only possible from the main buffer')
        return
    docids = set()
    for line in main_buf[lineFrom - 1:lineTo]:
        docid = get_docid(line)
        ref.delete_document(docid)
        docids.add(docid)

    for i, line in enumerate(main_buf):
        id = get_docid(line)
        if id in docids:
            del main_buf[i]


def insert_tag(tag):
    for i, line in enumerate(info_buf):
        if line.startswith('tags='):
            info_buf[i] += '{}; '.format(tag)
    save_info(parse_info())


def toggle_unread():
    for i, line in enumerate(info_buf):
        if line.startswith('rating='):
            info_buf[i] = 'rating=' + ('' if info_buf[i].endswith('U') else 'U')
    save_info(parse_info())
    


def order_documents(o):
    global order

    order = o
    last_select_cmd()

ref.init()

order = 'docid DESC'
headers = ('docid', 'rating', 'author', 'title', 'year')
tags = ref.get_tags()
col_size = {}

c = vim.command
c('set buftype=nofile')
c('set bufhidden=hide')
c('setlocal noswapfile')
c('file main')
main_buf, main_win = vim.current.buffer, vim.current.window
c('below new info') 
c('set buftype=nofile')
c('set bufhidden=hide')
c('setlocal noswapfile')
info_buf, info_win = vim.current.buffer, vim.current.window
c(':1winc w')

resize()
reload_main()
#ref.check_filenames()

c('autocmd CursorMoved main python3 write_info(selected_document())')
c('autocmd BufLeave,VimLeave info python3 save_info(parse_info())')
c('autocmd VimResized * python3 resize()')
c('set cursorline')
c('set wildmode=longest,list')
c('map q :qa!<CR>')
c('map <c-o> :python3 open_document()<CR>')
c('map <c-u> :python3 toggle_unread()<CR>')
c('map <c-w>o <NOP>')
c('map // :Search ')
c('com Fetch py fetch_bibtex()')
c('com -nargs=1 -complete=customlist,Tag Tag py insert_tag("<args>")')
c("com -nargs=? -complete=customlist,Tag Search py search_documents('''<args>''')")
c('com -nargs=? -complete=customlist,Column Order py order_documents("<args>")')
c('com -nargs=1 -complete=file Add py add_document("<args>")')
c('com -nargs=1 -complete=file Addd py add_document_del("<args>")')
c('com -nargs=1 -complete=file Addf py add_folder("<args>")')
c('com -nargs=1 -complete=file Addfd py add_folder_del("<args>")')
c('com -nargs=1 -complete=file Adda py add_arxiv("<args>")')
c('com -nargs=1 -complete=file Export py export_bib("<args>")')
c('com -range Delete py delete_document(<line1>, <line2>)')
c('set nonumber')

c('''function Tag(ArgLead, CmdLine, CursorPos)
    python3 c('let xs = {}'.format(list(tags)))
    return filter(xs, 'a:ArgLead == strpart(v:val, 0, strlen(a:ArgLead))')
endfunction''')

c('''function Column(ArgLead, CmdLine, CursorPos)
    let xs = {}
    return filter(xs, 'a:ArgLead == strpart(v:val, 0, strlen(a:ArgLead))')
endfunction'''.format([h for h in headers]))

