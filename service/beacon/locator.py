from __future__ import division
import ast, math

class Measurement(object):
    def __init__(self, d):
        self.d = d

    def distanceTo(self, other):
        sharedKeys = set(self.d).intersection(other.d)
        return math.sqrt(sum((other.d[f] - self.d[f])**2 for f in sharedKeys))
        
class Locator(object):
    def __init__(self):
        self.points = {} # num : (meas, coord)
        for lineLev, lineCoord in zip(open('saved_points'), open('saved_points_coords')):
            n, d = lineLev.split(None, 1)
            c = ast.literal_eval(lineCoord)
            if c['num'] != int(n):
                raise ValueError("%r vs %r" % (lineLev, lineCoord))
            self.points[c['num']] = (Measurement(ast.literal_eval(d)),
                                     (round(c['x'], 3), round(c['y'], 3), round(c['z'], 3)))
        for junk in [1, 2, 28, 29]:
            del self.points[junk]

    def nearestPoints(self, meas):
        out = []  # (dist, coord)
        for num, (knownMeas, coord) in self.points.iteritems():
            out.append((round(knownMeas.distanceTo(meas), 2), coord))
        out.sort()
        return out

    def estimatePosition(self, nearest):
        """list of (dist, coord) -> weighted coord"""
        floors = [row[1][2] for row in nearest]
        freqs = [(floors.count(z), z) for z in floors]
        freqs.sort()
        bestFloor = freqs[-1][1]
        sameFloorMatches = [(dist, coord) for dist, coord in nearest
                            if coord[2] == bestFloor]
        sameFloorMatches.sort()
        sameFloorMatches = sameFloorMatches[:3]

        weightedCoord = [0, 0, 0]
        totalWeight = 0
        for dist, coord in sameFloorMatches:
            weight = (1 / (dist - sameFloorMatches[0][0] + .2))
            totalWeight += weight
            for i in range(3):
                weightedCoord[i] += weight * coord[i]
        for i in range(3):
            weightedCoord[i] /= totalWeight
        return weightedCoord
        
if __name__ == '__main__':
    loc = Locator()
    for row in loc.nearestPoints(Measurement({"bed":-78.2,"changing":-90.2,"living":-68})):
        print row
    
    
