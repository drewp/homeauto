#!/my/proj/homeauto/service/frontDoorArduino/bin/python
from pymongo import Connection
from dateutil.tz import tzlocal
import restkit, time, datetime
from web.utils import datestr

c3po = restkit.Resource('http://bang:9040/')
sensor = Connection("bang", 27017, tz_aware=True)['house']['sensor']

lastSent = None

while True:
    q = {"name":"frontDoor", "state":"open"}
    if lastSent is not None:
        q['t'] = {"$gt":lastSent}

    for row in sensor.find(q).sort([('t',-1)]).limit(1):
        t = row['t'].astimezone(tzlocal())
        msg = "front door opened at %s" % t.replace(microsecond=0).time().isoformat()
        if lastSent is not None:
            msg += " (previous was %s)" % datestr(lastSent, datetime.datetime.now(tzlocal()))
        for u in ["http://bigasterisk.com/foaf.rdf#drewp", "http://bigasterisk.com/kelsi/foaf.rdf#kelsi"]:
            c3po.post(path='', payload=dict(msg=msg, user=u, mode='email'))
        
        lastSent = row['t']
        
    time.sleep(1)
