# BLE iBeaconScanner based on https://github.com/adamf/BLE/blob/master/ble-scanner.py
# JCS 06/07/14
# Adapted for Python3 by Michael duPont 2015-04-05

#DEBUG = False
# BLE scanner based on https://github.com/adamf/BLE/blob/master/ble-scanner.py
# BLE scanner, based on https://code.google.com/p/pybluez/source/browse/trunk/examples/advanced/inquiry-with-rssi.py

# https://github.com/pauloborges/bluez/blob/master/tools/hcitool.c for lescan
# https://kernel.googlesource.com/pub/scm/bluetooth/bluez/+/5.6/lib/hci.h for opcodes
# https://github.com/pauloborges/bluez/blob/master/lib/hci.c#L2782 for functions used by lescan

import struct
import sys
import time
import bluetooth._bluetooth as bluez
import datetime
from dateutil.tz import tzlocal
from bson.binary import Binary
from influxdb import InfluxDBClient
from pymongo import MongoClient
from repoze.lru import LRUCache

LE_META_EVENT = 0x3e
OGF_LE_CTL=0x08
OCF_LE_SET_SCAN_ENABLE=0x000C

# these are actually subevents of LE_META_EVENT
EVT_LE_CONN_COMPLETE=0x01
EVT_LE_ADVERTISING_REPORT=0x02

def hci_enable_le_scan(sock):
    enable = 0x01
    cmd_pkt = struct.pack("<BB", enable, 0x00)
    bluez.hci_send_cmd(sock, OGF_LE_CTL, OCF_LE_SET_SCAN_ENABLE, cmd_pkt)


# ported from android/source/external/bluetooth/hcidump/parser/hci.c

def evttype2str(etype):
    return {
            0x00: "ADV_IND", # Connectable undirected advertising
            0x01: "ADV_DIRECT_IND", # Connectable directed advertising
            0x02: "ADV_SCAN_IND", # Scannable undirected advertising
            0x03: "ADV_NONCONN_IND", # Non connectable undirected advertising
            0x04: "SCAN_RSP", # Scan Response
    }.get(etype, "Reserved")

def bdaddrtype2str(btype):
    return {
            0x00: "Public",
            0x01: "Random",
            }.get(btype, "Reserved")


# from https://github.com/google/eddystone/blob/master/eddystone-url/implementations/linux/scan-for-urls

schemes = [
        "http://www.",
        "https://www.",
        "http://",
        "https://",
        ]

extensions = [
        ".com/", ".org/", ".edu/", ".net/", ".info/", ".biz/", ".gov/",
        ".com", ".org", ".edu", ".net", ".info", ".biz", ".gov",
        ]

def decodeUrl(encodedUrl):
    """
    Decode a url encoded with the Eddystone (or UriBeacon) URL encoding scheme
    """

    decodedUrl = schemes[encodedUrl[0]]
    for c in encodedUrl[1:]:
        if c <= 0x20:
            decodedUrl += extensions[c]
        else:
            decodedUrl += chr(c)

    return decodedUrl

def decodeBeacon(data, row):
    # this padding makes the offsets line up to the scan-for-urls code
    padData = map(ord, '*' * 14 + data)
    
    # Eddystone
    if len(padData) >= 20 and padData[19] == 0xaa and padData[20] == 0xfe:
        serviceDataLength = padData[21]
        frameType = padData[25]

        # Eddystone-URL
        if frameType == 0x10:
            row["Eddystone-URL"] = decodeUrl(padData[27:22 + serviceDataLength])
        elif frameType == 0x00:
            row["Eddystone-UID"] = Binary(data)
        elif frameType == 0x20:
            row["Eddystone-TLM"] = Binary(data)
        else:
            row["Eddystone"] = "Unknown Eddystone frame type: %r data: %r" % (frameType, data)

    # UriBeacon
    elif len(padData) >= 20 and padData[19] == 0xd8 and padData[20] == 0xfe:
        serviceDataLength = padData[21]
        row["UriBeacon"] = decodeUrl(padData[27:22 + serviceDataLength])

    else:
        pass # "Unknown beacon type"

def decodeInquiryData(data, row):
    # offset 19 is totally observed from data, not any spec. IDK if the preceding part is variable-length.
    if len(data) > 20 and data[19] in ['\x08', '\x09']:
        localName = data[20:]
        if data[19] == '\x08':
            row['local_name_shortened'] = Binary(localName)
        else:
            row['local_name_complete'] = Binary(localName)
    # more at android/source/external/bluetooth/hcidump/parser/hci.c  ext_inquiry_data_dump

# from android/source/external/bluetooth/hcidump/parser/hci.c
def evt_le_advertising_report_dump(frm):
    num_reports = ord(frm[0])
    frm = frm[1:]

    for i in range(num_reports):
        fmt = 'B B 6B B'
        row = {}

        evt_type, bdaddr_type, b5, b4, b3, b2, b1, b0, length = struct.unpack(fmt, frm[:struct.calcsize(fmt)])
        frm = frm[struct.calcsize(fmt):]

        row['addr'] = '%02x:%02x:%02x:%02x:%02x:%02x' % (b0, b1, b2, b3, b4, b5)
        row['addr_type'] = bdaddrtype2str(bdaddr_type)
        row['evt_type'] = evttype2str(evt_type)

        data = frm[:length]
        frm = frm[length:]
        row['data'] = Binary(data)
        #row['data_hex'] = ' '.join('%02x' % ord(c) for c in data)

        decodeBeacon(data, row)
        decodeInquiryData(data, row)

        row['rssi'], = struct.unpack('b', frm[-1])
        frm = frm[1:]
        yield row



def parse_events(sock, loop_count, source, influx, coll, lastDoc):
    old_filter = sock.getsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, 14)
    flt = bluez.hci_filter_new()
    bluez.hci_filter_all_events(flt)
    bluez.hci_filter_set_ptype(flt, bluez.HCI_EVENT_PKT)
    sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, flt )

    points = []
    for i in range(0, loop_count):
        pkt = sock.recv(255)
        ptype, event, plen = struct.unpack("BBB", pkt[:3])
        now = datetime.datetime.now(tzlocal())
        nowMs = int(time.time() * 1000)
        if event == bluez.EVT_INQUIRY_RESULT_WITH_RSSI:
            print "EVT_INQUIRY_RESULT_WITH_RSSI"
        elif event == bluez.EVT_NUM_COMP_PKTS:
            print "EVT_NUM_COMP_PKTS"
        elif event == bluez.EVT_DISCONN_COMPLETE:
            print "EVT_DISCONN_COMPLETE"
        elif event == LE_META_EVENT:
            subevent, = struct.unpack("B", pkt[3:4])
            pkt = pkt[4:]
            if subevent == EVT_LE_CONN_COMPLETE:
                pass
            elif subevent == EVT_LE_ADVERTISING_REPORT:
                rows = list(evt_le_advertising_report_dump(pkt))
                for row in sorted(rows):
                    rssi = row.pop('rssi')
                    if row['addr_type'] == 'Public': # or, someday, if it's a device we know
                        points.append(dict(
                            measurement='rssi',
                            tags={'from': source, 'toAddr': row['addr']},
                            fields={'value': rssi},
                            time=nowMs,
                            ))
                        key = (row['addr'], row['evt_type'])
                        if lastDoc.get(key) != row:
                            # should check mongodb here- maybe another
                            # node already wrote this row
                            lastDoc.put(key, row)
                            row = row.copy()
                            row['t'] = now
                            coll.insert(row)

    influx.write_points(points, time_precision='ms')
    sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, old_filter )


if __name__ == '__main__':
    mongoHost, myLocation = sys.argv[1:]

    influx = InfluxDBClient(mongoHost, 9060, 'root', 'root', 'beacon')
    client = MongoClient(mongoHost)
    coll = client['beacon']['data']

    dev_id = 0
    sock = bluez.hci_open_dev(dev_id)
    sock.getsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, 14)

    hci_enable_le_scan(sock)

    lastDoc = LRUCache(1000) # (addr, evt_type) : data row
    while True:
        parse_events(sock, 10, source=myLocation, coll=coll, influx=influx, lastDoc=lastDoc)
