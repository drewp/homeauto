config = {
    'streams': [
        {'id': 'home',
         'sources': [
             # should be from :reasoning :source ?s
            #  'http://bang:9059/graph/events',
            #  'http://bang5:10310/graph/events', # kitchen
            #  'http://bang5:10311/graph/events', # living
            #  'http://bang5:10312/graph/events', # frontdoor
            #  'http://bang5:10313/graph/events', # workshop
            #  'http://bang5:10314/graph/events', # garage
            #  'http://bang5:10315/graph/events', # bed
            #  'http://bang5:10316/graph/events', # changing
            #  'http://bang5:10317/graph/events', # frontbed

            #  #'http://bang:9099/graph/mapTrails/events',
            #  'http://slash:9095/graph/dpms/events',
            #  'http://slash:9107/graph/xidle/events',
            #  'http://dash:9095/graph/dpms/events',
            #  'http://dash:9107/graph/xidle/events',
            #  'http://frontdoor5:9095/graph/dpms/events',
            #  'http://frontdoor5:9107/graph/xidle/events',
            #  'http://frontdoor5:10012/graph/rfid/events',
            #  'http://frontdoor5:10013/graph/tinyScreen/events',

            #  'http://bang:9075/graph/environment/events',
            #  'http://bang:10011/graph/frontDoorLock/events',
             'http://mqtt-to-rdf.default.svc.cluster.local.:10018/graph/mqtt/events',
            #  'http://bang:10016/graph/power/events',
            #  'http://bang:10015/graph/store/events',
            #  'http://bang:10006/graph/timebank/events',
            #  'http://bang:9070/graph/wifi/events',
         ]},
        {'id': 'frontDoor', # used for front door display
         'sources': [
            #  'http://bang:9105/graph/calendar/countdown/events',
            #  'http://bang:9105/graph/calendar/upcoming/events',
            #  'http://bang:9075/graph/environment/events',
             'http://mqtt-to-rdf.default.svc.cluster.local.:10018/graph/mqtt/events',
            #  'http://bang:10016/graph/power/events',
            #  'http://bang:10006/graph/timebank/events',
            #  'http://bang:10015/graph/store/events',

            #  'http://bang:9059/graph/events',
            #  'http://bang5:10310/graph/events', # kitchen
            #  'http://bang5:10311/graph/events', # living
            #  'http://bang5:10313/graph/events', # workshop
            #  'http://bang5:10314/graph/events', # garage
            #  'http://bang5:10317/graph/events', # frontbed
         ]},
        {'id': 'network',
         'sources': [
            #  'http://bang:9070/graph/wifi/events',
            #  'http://bang:9073/graph/dhcpLeases/events',
            #  'http://bang:9009/graph/traffic/events',
         ]},
        {'id': 'source_frontDoor',
         'sources': [
            #  'http://bang5:10312/graph/events', # frontdoor
            #  'http://frontdoor5:9095/graph/dpms/events',
            #  'http://frontdoor5:9107/graph/xidle/events',
            #  'http://frontdoor5:10012/graph/rfid/events',
            #  'http://frontdoor5:10013/graph/tinyScreen/events',
            #  'http://bang:10011/graph/frontDoorLock/events',
             'http://mqtt-to-rdf.default.svc.cluster.local.:10018/graph/mqtt/events',
         ]},
        {'id': 'env',
         'sources': [
            #  'http://bang:9075/graph/environment/events',
         ]},
        {'id': 'workshop',
         'sources': [
            #  'http://bang5:10313/graph/events', # workshop
         ]},

    ]
}
