from subprocess import Popen, PIPE
import os
import re
import shutil
import sqlite3
import sys
import vim

sys.path.append('/home/jure/devel/library')
import library


def parse_info():
    bibtex, rest = '\n'.join(info_buf).split('\n}\n', 1)
    doc = {'bibtex': bibtex + '\n}'}
    doc.update(dict(re.findall(r'(\w+)=(.*)', rest)))
    for k, v in doc.items():
        doc[k] = v.decode('utf8')
    doc['rowid'] = int(doc['rowid'])
    return doc


def write_info(doc):
    buf = doc['bibtex'].encode('utf8').splitlines()
    if not buf:
        buf = ['@{', '  title={}', '}']
    for attr in ('rowid', 'rating', 'filename'):
        val = doc[attr] or ''
        if isinstance(val, unicode):
            val = val.encode('utf8')
        buf.append('{}={}'.format(attr, val))
    info_buf[:] = buf


def str_document(doc):
    hdr = ('rowid', 'rating', 'title', 'author', 'year')
    cols = (str(doc[h] or '')[:col_size[h]].ljust(col_size[h]) for h in hdr)
    return '  '.join(cols)


def selected_document():
    rowid = int(main_buf[main_win.cursor[0] - 1].split()[0])
    return library.select_documents(id=rowid)[0]


def save_info(doc):
    library.update_document(doc)
    update_main(doc['rowid'])


def resize():
    global col_size

    info_win.height = 15
    col_size = {'year': 4, 'rowid': 3, 'rating': 2}
    left = main_win.width - sum(col_size.values()) - 2 * len(col_size) - 2
    col_size['author'] = int(round(left * 0.2))
    col_size['title'] = left - col_size['author']
    update_main()


def update_main(rowid=None):
    #TODO: check if this is slow for rowid=None
    for i, line in enumerate(main_buf):
        try:
            id = int(line.split()[0])
        except (ValueError, IndexError):
            continue
        if not rowid or rowid == id:
            doc = library.select_documents(id)[0]
            main_buf[i] = str_document(doc)


def reload_main():
    main_buf[:] = [str_document(doc) for doc in library.select_documents()]


def fetch_bibtex():
    doc = parse_info()
    title = library.parse_bibtex(doc['bibtex'])['title']
    doc['bibtex'] = library.fetch_bibtex(title)
    save_info(doc)
    write_info(doc)


def open_document():
    filename = selected_document()['filename']
    Popen(['xdg-open', os.path.join(library.DOCUMENT_DIR, filename)], stderr=PIPE, stdout=PIPE)


c = vim.command

c('set buftype=nofile')
c('file main')
main_buf, main_win = vim.current.buffer, vim.current.window
c('below new info') 
c('set buftype=nofile')
info_buf, info_win = vim.current.buffer, vim.current.window

c(':1winc w')
resize()
reload_main()

c('autocmd CursorMoved main python write_info(selected_document())')
c('autocmd BufLeave,VimLeave info python save_info(parse_info())')
c('autocmd VimResized * python resize()')
c('map <c-x> :qa!<CR>')
c('map <c-m> 1<c-w><c-w>')
c('map <c-i> 2<c-w><c-w>')
c('map <c-o> :python open_document()<CR>')
c('command Fetch py fetch_bibtex()')
