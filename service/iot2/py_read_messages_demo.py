import sys
import capnp
# (No compile step)
messages_capnp = capnp.load('messages.capnp')
print(dir(messages_capnp))

report = messages_capnp.Report.new_message()
report.sensor = b'hello'
report.value = 1.234
print(repr(report.to_bytes()))
