
import web, json
import time

from p2ptrade import *

urls = ('/messages', 'jsonapi')

app = web.application(urls, globals())

class TextfileDatabaseHandler():
    def __init__(self,filename):
        try:
            self.data = json.loads(open(filename,'r').read())
        except:
            open(filename,'w').write('')
            fileobj = open(filename,'r')        
            self.data = {}
        self.filename = filename
    def save(self):
        open(self.filename,'w').write(json.dumps(self.data))
    def get(self,key):
        return self.data.get(str(key),None)
    def listkeys(self):
        return self.data.keys()
    def put(self,key,val,save=True):
        self.data[str(key)]=val
        if save: self.save()

db = TextfileDatabaseHandler('db.txt')

class jsonapi:
    def GET(self):
        id = web.input(id=None).id
        from_timestamp = int(web.input(from_timestamp=-1).from_timestamp)
        from_serial = int(web.input(from_serial=-1).from_serial)
        data = db.get('messages') or []
        maxnum = 25 if from_timestamp == -1 and from_serial == -1 else 9999
        def filterf(x):
          if id is not None and x.get('id') != id: return False
          if x.get('timestamp',0) < from_timestamp: return False
          if x.get('serial',0) < from_serial: return False
          return True
        data = filter(filterf,data)
        return json.dumps(sorted(data,key=lambda x:-x['timestamp'])[:maxnum])
        
    def POST(self):
        data = web.data()
        try:
            print data
            obj = json.loads(data)
            try: id = str(obj["oid"])
            except:
              try: id = str(obj["offer"]["oid"])
              except: id = "0"
            print 0
            serial = db.get('last_serial') or 0
            print 1
            existing = db.get('messages') or []
            print 2
            new = [{'id':id,'timestamp':int(time.time()),'serial':serial+1,'content':obj}]
            db.put('last_serial',serial+1,False)
            db.put('messages',existing + new)
            return 'Success'
        except:
            return 'Failure'

if __name__ == '__main__':
    app.run()

