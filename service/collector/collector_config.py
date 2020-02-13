config = {
    'streams': [
        {'id': 'home',
         'sources': [
             # should be from :reasoning :source ?s

             'http://bang:9059/graph/events',
             'http://bed5:9059/graph/events',
             'http://changing5:9059/graph/events',
             'http://frontbed5:9059/graph/events',
             'http://frontdoor5:9059/graph/events',
             'http://garage5:9059/graph/events',
             'http://kitchen5:9059/graph/events',
             'http://living5:9059/graph/events',
             'http://workshop5:9059/graph/events',

             #'http://bang:9099/graph/mapTrails/events',
             'http://slash:9095/graph/dpms/events',
             'http://slash:9107/graph/xidle/events',
             'http://dash:9095/graph/dpms/events',
             'http://dash:9107/graph/xidle/events',
             'http://frontdoor5:9095/graph/dpms/events',
             'http://frontdoor5:9107/graph/xidle/events',
             'http://frontdoor5:10012/graph/rfid/events',
             'http://frontdoor5:10013/graph/tinyScreen/events',

             'http://bang:9075/graph/environment/events',
             'http://bang:10011/graph/frontDoorLock/events',
             'http://bang:10018/graph/mqtt/events',
             'http://bang:10016/graph/power/events',
             'http://bang:10015/graph/store/events',
             'http://bang:10006/graph/timebank/events',
             'http://bang:9070/graph/wifi/events',
         ]},
        {'id': 'frontDoor', # used for front door display
         'sources': [
             'http://bang:9105/graph/calendar/countdown/events',
             'http://bang:9105/graph/calendar/upcoming/events',
             'http://bang:9075/graph/environment/events',
             'http://bang:10018/graph/mqtt/events',
             'http://bang:10016/graph/power/events',
             'http://bang:10006/graph/timebank/events',
             'http://bang:10015/graph/store/events',

             'http://bang:9059/graph/events',
             'http://frontbed5:9059/graph/events',
             'http://garage5:9059/graph/events',
             'http://kitchen5:9059/graph/events',
             'http://living5:9059/graph/events',
             'http://workshop5:9059/graph/events',
         ]},
        {'id': 'network',
         'sources': [
             'http://bang:9070/graph/wifi/events',
             'http://bang:9073/graph/dhcpLeases/events',
             'http://bang:9009/graph/traffic/events',
         ]},
        {'id': 'source_frontDoor',
         'sources': [
             'http://frontdoor5:9059/graph/events',
             'http://frontdoor5:9095/graph/dpms/events',
             'http://frontdoor5:9107/graph/xidle/events',
             'http://frontdoor5:10012/graph/rfid/events',
             'http://frontdoor5:10013/graph/tinyScreen/events',
             'http://bang:10011/graph/frontDoorLock/events',
             'http://bang:10018/graph/mqtt/events',
         ]},
        {'id': 'env',
         'sources': [
             'http://bang:9075/graph/environment/events',
         ]},
        {'id': 'workshop',
         'sources': [
             'http://workshop5:9059/graph/events',
         ]},

    ]
}
