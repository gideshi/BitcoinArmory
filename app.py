
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
        if id is not None: 
            data = db.get(id) or []
        else:
            data = reduce(lambda x,y:x+y, [[]]+[db.get(k) for k in db.listkeys()])
        return json.dumps(sorted(data,key=lambda x:-x['timestamp'])[:25])
        
    def POST(self):
        data = web.data()
        try:
            obj = json.loads(data)
            try: id = str(obj["oid"])
            except:
              try: id = str(obj["pid"])
              except: id = "0"
            existing = db.get(id) or []
            new = [{'id':id,'timestamp':int(time.time()),'content':obj}]
            db.put(id,existing + new)
            return 'Success'
        except:
            return 'Failure'

if __name__ == '__main__':
    app.run()

