import web, json

urls = ('/messages', 'json')

app = web.application(urls, globals())

class TextfileDatabaseHandler():
    def __init__(self,filename):
        self.data = json.loads(open(filename,'r').read())
        self.filename = filename
    def save(self):
        open(self.filename,'w').write(json.dumps(self.data))
    def get(key):
        return self.data.get(key,None)
    def listkeys(self):
        return self.data.keys()
    def put(key,val,save=True):
        self.data[key]=val
        if save: self.save()

def serialize(obj):
    # Should convert object to string representation
    return obj

def deserialize(data):
    # Should convert string representation to object
    return data

class json:
    db = TextfileDatabaseHandler('db.txt')
    def GET(self,id=None):
        if id: 
            data = db.get(id)
        else:
            data = reduce(lambda x,y:x+y, [db.get(k) for k in db.listkeys()])
        print json.dumps(sorted(data,key=lambda x:-x['timestamp'])[:25])
        
    def POST(self):
        data = web.data()
        try:
            obj = deserialize(data)
            try: id = obj.oid
            except: id = obj.offer.oid
            db.put(id,data)
            return 'Success'
        except:
            return 'Failure'

if __name__ == '__main__':
    app.run()

