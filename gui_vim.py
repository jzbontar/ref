import vim
import sqlite3

def cursor_moved():
    global id

    id = vim.current.line
    if not id:
        return
    cur.execute('select data from data where id=?', (id,))
    res = cur.fetchone()
    if res:
        info_buf[0] = str(res[0])
    else:
        cur.execute('insert into data (id, data) values (?, "")', (id,))

def write_info():
    cur.execute('update data set data=? where id=?', (info_buf[0], id))

def close():
    conn.commit()
    cur.close()

c = vim.command

conn = sqlite3.connect('/tmp/data')
cur = conn.cursor()
if 0:
    cur.execute('drop table if exists data')
    cur.execute('create table data (id text primary key, data text)')
    for d in [('jure', 'zbontar'), ('minca', 'mramor'), ('rea', 'kolb')]:
        cur.execute('insert into data values (?, ?)', d)

c('set buftype=nofile')
c('file info')
c('new main')
c('set buftype=nofile')
info_buf = vim.buffers[0]
main_buf = vim.buffers[1]
vim.windows[1].height = 16

cur.execute('select id from data')

main_buf[:] = [str(res[0]) for res in cur.fetchall()]
 
c('autocmd CursorMoved main python cursor_moved()')
c('autocmd BufLeave,VimLeave info python write_info()')
c('autocmd VimLeave * python close()')
c('map X :qa!<CR>')
