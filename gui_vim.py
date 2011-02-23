import sqlite3
import sys
import vim
import re

sys.path.append('/home/jure/devel/library')
import document


def parse_bibtex(bibtex):
    reg = r'^\s*(title|author|year)={*(.+?)}*,?$'
    return dict(re.findall(reg, bibtex, re.MULTILINE))


def parse_info():
    bibtex, info = '\n'.join(info_buf).decode('utf8').split('\n\n', 1)
    info = dict(re.findall(r'(\w+)=(.*)', info))

    return bibtex, info


def write_info(bibtex, info):
    buf = bibtex.encode('utf8').splitlines()
    buf.extend([''] + ['{}={}'.format(k, v) for k, v in info.items()])
    info_buf[:] = buf


def str_document(id, bibtex):
    row = parse_bibtex(bibtex)
    row['id'] = id

    hdr = (u'id', u'author', u'title', u'year')
    return '  '.join(str(row.get(h, ''))[:col_size[h]].ljust(col_size[h]) for h in hdr)


def cursor_moved():
    id = int(vim.current.line.split()[0])
    cur.execute('SELECT bibtex FROM documents WHERE ROWID=?', (id,))
    bibtex = cur.fetchone()[0]
    write_info(bibtex, {'id': id})


def save_info(bibtex, info):
    cur.execute('update documents set bibtex=? where ROWID=?', (bibtex, info['id']))
    for i, line in enumerate(main_buf):
        if line.split()[0] == info['id']:
            main_buf[i] = str_document(info['id'], bibtex)


def reload_main():
    global col_size

    col_size = {'year': 4, 'id': 3}
    left = main_win.width - sum(col_size.values()) - 2 * len(col_size) - 2
    col_size['author'] = int(round(left * 0.2))
    col_size['title'] = left - col_size['author']
    cur.execute('select ROWID, bibtex from documents')
    main_buf[:] = [str_document(*res) for res in cur.fetchall()]


def fetch_bibtex():
    bibtex, info = parse_info()
    title = parse_bibtex(bibtex)['title']
    bibtex = document.fetch_bibtex(title)
    save_info(bibtex, info)
    write_info(bibtex, info)

BASE_DIR = os.path.expanduser('~/.library/')
DOCUMENT_DIR = os.path.join(BASE_DIR, 'documents/')
DB_FILE = os.path.join(BASE_DIR, 'db.sqlite3')

conn = sqlite3.connect(DB_FILE)
conn.isolation_level = None
cur = conn.cursor()

for dir in (BASE_DIR, DOCUMENT_DIR):
    if not os.path.exists(dir):
        os.mkdir(dir)


c = vim.command

c('set buftype=nofile')
c('file main')
main_buf, main_win = vim.current.buffer, vim.current.window
c('below new info') 
c('set buftype=nofile')
info_buf, info_win = vim.current.buffer, vim.current.window

info_win.height = 20

c(':1winc w')
reload_main()
 
c('autocmd CursorMoved main python cursor_moved()')
c('autocmd BufLeave,VimLeave info python save_info(*parse_info())')
c('map X :qa!<CR>')
c('map <c-k> 1<c-w><c-w>')
c('map <c-j> 2<c-w><c-w>')
c('command Fetch py fetch_bibtex()')
