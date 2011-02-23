import sqlite3
import sys
import vim
import re

sys.path.append('/home/jure/devel/library')
import extern


def parse_bibtex(bibtex):
    reg = r'^\s*(title|author|year)={+(.+?)}+,?$'
    return dict(re.findall(reg, bibtex, re.MULTILINE))


def str_document(id, bibtex):
    row = parse_bibtex(bibtex)
    row['id'] = id

    hdr = ('id', 'author', 'title', 'year')
    return '  '.join(str(row[h])[:col_size[h]].ljust(col_size[h]) for h in hdr)


def cursor_moved():
    id = int(vim.current.line.split()[0])
    cur.execute('SELECT bibtex FROM documents WHERE ROWID=?', (id,))
    out = cur.fetchone()[0].encode(errors='replace').splitlines()
    out.extend(['', 'id={}'.format(id)])
    info_buf[:] = out


def write_info():
    bibtex, info = '\n'.join(info_buf).decode().split('\n\n', 1)

    info = dict(re.findall(r'(\w+)=(.*)', info))
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
    


c = vim.command
cur = extern.conn.cursor()

c('set buftype=nofile')
c('file main')
main_buf, main_win = vim.current.buffer, vim.current.window
c('below new tags')
c('set buftype=nofile')
tags_buf, tags_win = vim.current.buffer, vim.current.window
c('vne info') 
c('set buftype=nofile')
info_buf, info_win = vim.current.buffer, vim.current.window

tags_win.height = 20
tags_win.width = 30

c(':1winc w')
reload_main()
 
c('autocmd CursorMoved main python cursor_moved()')
c('autocmd BufLeave,VimLeave info python write_info()')
c('map X :qa!<CR>')
c('map <c-m> 1<c-w><c-w>')
c('map <c-i> 2<c-w><c-w>')
c('map <c-t> 3<c-w><c-w>')
