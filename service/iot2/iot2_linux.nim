import nimpy

proc setup_python(): PyObject =
  let sys = pyImport("sys")
  discard sys.path.extend([
    ".", # for devices.py itself
    "env/lib/python3.7/site-packages" # for deeper imports
  ])

  pyImport("devices")


echo "iot2_linux starting"

let devices = setup_python()
discard devices.hello()
