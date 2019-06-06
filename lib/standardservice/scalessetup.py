import time
from greplin import scales
from twisted.internet import task
import psutil

def gatherProcessStats():
    procStats = scales.collection('/process',
                                  scales.DoubleStat('time'),
                                  scales.DoubleStat('cpuPercent'),
                                  scales.DoubleStat('memMb'),
    )
    proc = psutil.Process()
    lastCpu = [0.]
    def updateTimeStat():
        now = time.time()
        procStats.time = round(now, 3)
        if now - lastCpu[0] > 3:
            procStats.cpuPercent = round(proc.cpu_percent(), 6) # (since last call)
            lastCpu[0] = now
        procStats.memMb = round(proc.memory_info().rss / 1024 / 1024, 6)
    task.LoopingCall(updateTimeStat).start(.1)
