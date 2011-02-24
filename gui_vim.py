from subprocess import Popen, PIPE
import os
import re
import sqlite3
import sys
import vim

sys.path.append('/home/jure/devel/library')
import library


def search(s):
    if not s:
        reload_main()
        return
    s = '%{}%'.format(s)
    del main_buf[:]
    fields = ('tags', 'title', 'author', 'fulltext')
    for field in fields:
        res = library.select_documents(headers, where='{} LIKE ?'.format(field), args=(s,))
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
    doc = {'bibtex': bibtex + '\n}'}
    for k, v in re.findall(r'(\w+)=(.*)', rest):
        doc[k.encode('utf8')] = v
    doc['rowid'] = int(doc['rowid'])
    return doc


def save_info(doc):
    library.update_document(doc)
    update_main((doc['rowid'],))


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
        buf = ['@{', '  title={}', '}']
    for attr in ('rowid', 'tags', 'rating', 'filename'):
        buf.append('{}={}'.format(attr, encode_val(doc[attr])))
    info_buf[:] = buf


def str_document(doc):
    cs = (encode_val(doc[h])[:col_size[h]].ljust(col_size[h]) for h in headers)
    return '  '.join(cs)


def selected_document():
    rowid = get_rowid(main_buf[main_win.cursor[0] - 1])
    if rowid:
        return library.select_documents(headers + ['bibtex', 'filename', 'tags'], rowids=(rowid,))[0]
    else:
        return None


def resize():
    global col_size

    info_win.height = 15
    col_size = {'year': 4, 'rowid': 3, 'rating': 2}
    left = main_win.width - sum(col_size.values()) - 2 * len(col_size) - 2
    col_size['author'] = int(round(left * 0.2))
    col_size['title'] = left - col_size['author']

    rowids = {get_rowid(line) for line in main_buf}
    update_main(rowids - {None})


def update_main(rowids):
    docs = {d['rowid']: d for d in library.select_documents(headers, rowids=rowids)}

    for i, line in enumerate(main_buf):
        id = get_rowid(line)
        if id and id in rowids:
            main_buf[i] = str_document(docs[id])


def reload_main():
    main_buf[:] = [str_document(doc) for doc in library.select_documents(headers)]


def fetch_bibtex():
    doc = parse_info()
    title = library.parse_bibtex(doc['bibtex'])['title']
    doc['bibtex'] = library.fetch_bibtex(title)
    save_info(doc)
    write_info(doc)


def open_document():
    filename = selected_document()['filename']
    Popen(['xdg-open', os.path.join(library.DOCUMENT_DIR, filename)], stderr=PIPE, stdout=PIPE)


def add_document(fname):
    rowid = library.insert_document(fname)
    doc = library.select_documents(headers, (rowid,))[0]
    main_buf[:0] = [str_document(doc)]


def delete_document():
    doc = selected_document()
    library.delete_document(doc)

    for i, line in enumerate(main_buf):
        id = get_rowid(line)
        if id == doc['rowid']:
            del main_buf[i]
            

c = vim.command
headers = ['rowid', 'rating', 'author', 'title', 'year']

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

c('autocmd CursorMoved main python write_info(selected_document())')
c('autocmd BufLeave,VimLeave info python save_info(parse_info())')
c('autocmd VimResized * python resize()')
c('set cursorline')
c('map <c-x> :qa!<CR>')
c('map <c-o> :python open_document()<CR>')
c('map <c-w>o <NOP>')
c('map // :Search ')
c('command Fetch py fetch_bibtex()')
c('command -nargs=? Search py search("<args>")')
c('command -nargs=1 -complete=file Add py add_document("<args>")')
c('command Delete py delete_document()')
