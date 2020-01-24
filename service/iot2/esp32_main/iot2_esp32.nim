
# the idea is that an ESP-IDF or esphome project calls C funcs defined
# here (that compile to .c files in build/nimcache/)

echo "hello on esp"
proc add(x: int, y: int): int =
  x + y
