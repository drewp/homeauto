import os, re
from subprocess import check_call
from tempfile import NamedTemporaryFile
from pymongo import Connection

def makeCode(s):
    #return 'code'
    psFile = NamedTemporaryFile(suffix='.ps')
    check_call(['barcode',
                '-b', s,
                '-E',
                '-o', psFile.name])
    svgFile = NamedTemporaryFile(suffix='.svg')
    check_call(['pstoedit',
                '-f', 'plot-svg',
                '-yshift', '580',
                '-xshift', '20',
                psFile.name, svgFile.name])
    lines = open(svgFile.name).readlines()
    return ''.join(lines[2:])

def codeElem(s):
    return '<div class="bc">%s</div>' % makeCode(s)

mpdPaths = Connection("bang", 27017)['barcodePlayer']['mpdPaths']
# {mpdPath:"music/path/to/album/or/song", "_id":12}
mpdPaths.ensure_index([('mpdPath', 1)])
def idForMpdPath(p):
    match = mpdPaths.find_one({"mpdPath" : p})
    if match:
        return match['_id']

    top = list(mpdPaths.find().sort([('_id', -1)]).limit(1))
    newId = top[0]['_id'] + 1 if top else 0
    mpdPaths.insert({"mpdPath" : p, "_id" : newId})
    return newId
            

out = open("out.xhtml", "w")
out.write("""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <title>barcodes</title>
    <link rel="stylesheet" href="barcode.css"/>
  </head>
  <body>
    <div class="cards">
""")


mpdRoot = "/my/music"

paths = open("mpdPaths.txt").read().strip().splitlines()

cardsSeen = 0
for path in paths:
    if os.path.isdir(os.path.join(mpdRoot, path)):
        albumDir = path.split('/')[-1]
        songFile = None
    else:
        albumDir, songFile = path.split('/')[-2:]

    if '-' in albumDir:
        artistName, albumName = albumDir.replace('_', ' ').split('-', 1)
    else:
        artistName, albumName = '', albumDir

    if artistName in ['', 'Original Soundtrack', 'Various']:
        artistName = albumName
        albumName = ''
        
    if songFile:
        songName = re.sub(r'(^\d+\.)|(^\d+\s*-)', '', songFile)
        songName = songName.rsplit('.',1)[0].replace('_', ' ')
    
    out.write('<div class="card">')
    out.write('<div class="artist">%s</div>' % artistName)
    out.write('<div class="album">%s</div>' % albumName)

    print (albumName, songName if songFile else '')
    out.write(codeElem("music %s" % idForMpdPath(path)))

    if songFile:
        out.write('<div class="song">%s</div>' % songName)

    out.write('</div>')
    cardsSeen += 1
    if cardsSeen % 8 == 0:
        out.write('<div class="pgbr"/>')
        
out.write("""
    </div>
  </body>
</html>
""")
