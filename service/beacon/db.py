from pymongo import MongoClient
from influxdb import InfluxDBClient
import arrow


from influxdb.resultset import ResultSet
# patch a crash where the row didn't seem to have enough Nones in it
def point_from_cols_vals(cols, vals):
    point = {}
    for col_index, col_name in enumerate(cols):
        try:
            point[col_name] = vals[col_index]
        except IndexError:
            point[col_name] = None
    return point
ResultSet.point_from_cols_vals = staticmethod(point_from_cols_vals)

class Db(object):
    def __init__(self, influxArgs=('bang', 9060, 'root', 'root', 'beacon'),
                 mongoArgs=('bang', 27017)):
        self.mongo = MongoClient(*mongoArgs, tz_aware=True)['beacon']['data']
        self.influx = InfluxDBClient(*influxArgs)

    def addrs(self, startTime):
        ret = set()
        for row in self.influx.query('''
              select *
              from "rssi"
              where time > '%s'
        ''' % (startTime.isoformat()))['rssi']:
            ret.add(row['toAddr'])
        return ret

    def _fixRow(self, row):
        row['time'] = arrow.get(row['time'])
        row['rssi'] = row.pop('max')
        
    def sensors(self):
        return [row['from'] for row in
                self.influx.query('SHOW TAG VALUES FROM "rssi" WITH KEY = "from"').get_points()]

    def recentRssi(self, startTime, toAddr=None):
        toAddrPredicate = (" and toAddr = '%s'" % toAddr) if toAddr else ''
        for row in self.influx.query('''
              select time,max(value),"from","toAddr"
              from "rssi"
              where time > '%s' %s
              group by time(2s), "from"
              order by time
            ''' % (startTime.isoformat(), toAddrPredicate))['rssi']:
            if row['max'] is not None:
                self._fixRow(row)
                yield row

    def latestDetail(self, addr):
        doc = self.mongo.find_one({'addr': addr}, sort=[('t', -1)])
        if not doc:
            return {}
        return doc
        
if __name__ == '__main__':
    import datetime
    from dateutil.tz import tzlocal
    db = Db()
    print db.addrs(datetime.datetime.now(tzlocal()) - datetime.timedelta(seconds=60*2))
    print list(db.recentRssi(datetime.datetime.now(tzlocal()) - datetime.timedelta(seconds=60*2)))
    print db.latestDetail('00:ea:23:23:c6:c4')
