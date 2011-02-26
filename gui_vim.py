from subprocess import Popen, PIPE
import os
import glob
import re
import sqlite3
import sys
import vim
import collections

sys.path.append('/home/jure/devel/ref')
import ref


def search(s):
    if not s:
        reload_main()
        return
    s = '%{}%'.format(s)
    del main_buf[:]
    fields = ('tags', 'title', 'author', 'journal', 'fulltext')
    for field in fields:
        res = ref.select_documents(headers, field + ' LIKE ?', (s,))
        if res:
            heading = '# {}'.format(field.upper())
            if len(main_buf) == 1:
                main_buf[:] = [heading]
            else:
                main_buf.append('')
                main_buf.append(heading)
            main_buf[len(main_buf):] = map(str_document, res)


def parse_info():
    bibtex, rest = '\n'.join(info_buf).decode('utf8').split('\n}\n', 1)
    doc = collections.defaultdict(unicode)
    doc['bibtex'] = bibtex + '\n}'
    for k, v in re.findall(r'(\w+)=(.*)', rest):
        doc[k.encode('utf8')] = v
    doc['rowid'] = int(doc['rowid'])
    tags.update(doc['tags'].split('; '))
    return doc


def save_info(doc):
    ref.update_document(doc)
    update_main('rowid=?', (doc['rowid'],))


def get_rowid(line):
    try:
        return int(line.split()[0])
    except (ValueError, IndexError):
        return None


def encode_val(val):
    return unicode(val).encode('utf8') if val else ''


def write_info(doc):
    if not doc:
        info_buf[:] = []
        return
    buf = doc['bibtex'].encode('utf8').splitlines()
    if not buf:
        buf = ['@{', '  title=', '}']
    for attr in ('rowid', 'tags', 'rating', 'filename'):
        buf.append('{}={}'.format(attr, encode_val(doc[attr])))
    info_buf[:] = buf


def str_document(doc):
    cs = (encode_val(doc[h])[:col_size[h]].ljust(col_size[h]) for h in headers)
    return '  '.join(cs)


def selected_document():
    rowid = get_rowid(main_buf[main_win.cursor[0] - 1])
    if rowid:
        return ref.select_documents(headers + ['bibtex', 'filename', 'tags'], 'rowid=?', (rowid,))[0]
    else:
        return None


def resize():
    global col_size

    info_win.height = 15
    col_size = {'year': 4, 'rowid': 4, 'rating': 2, 'author': 30}
    col_size['title'] = main_win.width - sum(col_size.values()) - 2 * len(col_size)

    if main_buf[0] and len(main_buf) > 1:
        update_main()


def update_main(where=None, args=()):
    docs = {d['rowid']: d for d in ref.select_documents(headers, where, args)}

    for i, line in enumerate(main_buf):
        id = get_rowid(line)
        if id in docs:
            main_buf[i] = str_document(docs[id])


def reload_main():
    main_buf[:] = [str_document(doc) for doc in ref.select_documents(headers)]


def fetch_bibtex():
    doc = parse_info()
    title = ref.parse_bibtex(doc['bibtex'])['title']
    doc['bibtex'] = ref.fetch_bibtex(title)
    save_info(doc)
    write_info(doc)


def open_document():
    filename = selected_document()['filename']
    Popen(['xdg-open', os.path.join(ref.DOCUMENT_DIR, filename)], stderr=PIPE, stdout=PIPE)


def add_document(fname):
    rowid = ref.insert_document(fname)
    if rowid:
        doc = ref.select_documents(headers, 'rowid=?', (rowid,))[0]
        main_buf[:0] = [str_document(doc)]
        main_win.cursor = (1, 0)


def delete_document(lineFrom, lineTo):
    rowids = set()
    for line in main_buf[lineFrom - 1:lineTo]:
        rowid = get_rowid(line)
        ref.delete_document(rowid)
        rowids.add(rowid)

    for i, line in enumerate(main_buf):
        id = get_rowid(line)
        if id in rowids:
            del main_buf[i]


def complete_tag(prefix):
    return [tag.encode('utf8') for tag in tags if tag.startswith(prefix)]


def insert_tag(tag):
    for i, line in enumerate(info_buf):
        if line.startswith('tags='):
            info_buf[i] += '{}; '.format(tag)
    save_info(parse_info())

            
headers = ['rowid', 'rating', 'author', 'title', 'year']
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

c('autocmd CursorMoved main python write_info(selected_document())')
c('autocmd BufLeave,VimLeave info python save_info(parse_info())')
c('autocmd VimResized * python resize()')
c('set cursorline')
c('set wildmode=longest,list')
c('map <c-x> :qa!<CR>')
c('map <c-o> :python open_document()<CR>')
c('map <c-w>o <NOP>')
c('map // :Search ')
c('com Fetch py fetch_bibtex()')
c('com -nargs=1 -complete=customlist,CompleteTag Tag py insert_tag("<args>")')
c('com -nargs=? -complete=customlist,CompleteTag Search py search("<args>")')
c('com -nargs=1 -complete=file Add py add_document("<args>")')
c('com -range Delete py delete_document(<line1>, <line2>)')

c('''function! CompleteTag(ArgLead, CmdLine, CursorPos)
    python c('return {}'.format(complete_tag(vim.eval('a:ArgLead'))))
endfunction''')
