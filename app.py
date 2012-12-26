
import web, json
import time
import os
import sqlite3

from p2ptrade import *

urls = ('/messages', 'jsonapi')

app = web.application(urls, globals())

def initdb(filename):
    try:
       d,f = os.path.split(filename)
       assert f in os.listdir(os.path.join(os.getcwd(),d))
       exists = True
    except:
       exists = False
    c = sqlite3.connect(filename)
    if not exists:
       print 'Creating database tables'
       c.execute('''CREATE TABLE messages
           (id bigint, timestamp bigint, serial bigint, content text)''')
       c.execute('''CREATE TABLE metadata
           (key text, value text)''')
       c.commit()

initdb('main.db')

class jsonapi:
    def GET(self):
        conn = sqlite3.connect('main.db')
        id = web.input(id=None).id
        from_timestamp = int(web.input(from_timestamp=-1).from_timestamp)
        from_serial = int(web.input(from_serial=-1).from_serial)
        maxnum = 25 if from_timestamp == -1 and from_serial == -1 else 99999
        if id is not None:
          rawdata = conn.execute('SELECT * From messages WHERE id = ? AND serial >= ? AND timestamp >= ?',
                     (id, from_serial, from_timestamp)).fetchall()
        else:
          rawdata = conn.execute('SELECT * From messages WHERE serial >= ? AND timestamp >= ?',
                     (from_serial, from_timestamp)).fetchall()
        data = [{'id':x[0],'timestamp':x[1],'serial':x[2],'content':x[3]} for x in rawdata]
        return json.dumps(sorted(data,key=lambda x:-x['timestamp'])[:maxnum])
        
    def POST(self):
        conn = sqlite3.connect('main.db')
        data = web.data()
        try:
            obj = json.loads(data)
            try: id = obj["oid"]
            except:
              try: id = obj["offer"]["oid"]
              except: id = 0
            serial = int((conn.execute('SELECT * From metadata WHERE key = "last_serial"').fetchone() or [0,0])[1])
            new = (id, int(time.time()),serial+1,data)
            conn.execute('DELETE From metadata WHERE key = "last_serial"')
            conn.execute('INSERT INTO metadata VALUES (?,?)',("last_serial",serial+1))
            conn.execute('INSERT INTO messages VALUES (?,?,?,?)',new)
            conn.commit()
            return 'Success'
        except:
            return 'Failure'

if __name__ == '__main__':
    app.run()

