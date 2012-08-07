"""
write the automatic last line to LCD /lastLine
"""
import sys, time
sys.path.append("/my/site/magma")
from datetime import datetime
from graphitetemp import getAllTemps

import restkit

# needs poller with status report

while True:
    fd = restkit.Resource("http://bang:9081/")

    allTemp = getAllTemps()
    now = datetime.now()

    line = "%02d:%02d %02dF in, %02dF out" % (now.hour, now.minute,
                                              allTemp.get('livingRoom', 0),
                                              allTemp.get('frontDoor', 0))
    fd.put("lastLine", payload=line)
    time.sleep(60)
