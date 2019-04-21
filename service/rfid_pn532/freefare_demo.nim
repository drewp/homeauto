import nfc-nim/nfc, nfc-nim/freefare

var m = freefare.mad_new(0)

echo(freefare.mad_get_version(m))

freefare.mad_free(m)
var context: ptr nfc.context
nfc.init(addr context)

var connstrings: array[10, nfc.connstring]
var n = nfc.list_devices(context, cast[ptr nfc.connstring](addr connstrings), len(connstrings))
echo(n)
#var dev = nfc.open(context, "pn532_i2c:/dev/i2c-1")
#echo(device_get_last_error(dev))

#nfc.close(dev)
nfc.exit(context)
