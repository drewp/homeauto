import nimpy

proc setup_python(): PyObject =
  let sys = pyImport("sys")
  discard sys.path.extend([
    ".", # for devices.py itself
    "build/py/lib/python3.7/site-packages" # for deeper imports
  ])

  pyImport("devices")

import json
import osproc
proc getSomeTemp(): float =
  let sensorsJson = execProcess("sensors", args=["-j"], options={poUsePath})
  let res = parseJson(sensorsJson)
  res["coretemp-isa-0000"]["Core 0"]["temp2_input"].getFloat





echo "iot2_linux starting"
echo getSomeTemp()
let devices = setup_python()
discard devices.hello()
