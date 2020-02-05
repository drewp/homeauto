config = {
    'streams': [
        {'id': 'home',
         'sources': [
             # should be from :reasoning :source ?s
             'http://garage5:9059/graph/events', # "garage pi"
             'http://kitchen5:9059/graph/events', # "kitchen pi"
             'http://living5:9059/graph/events', # "living room pi"
             'http://bang:9059/graph/events', # "bang arduino"
             'http://bed5:9059/graph/events', # "bed pi"
             'http://changing5:9059/graph/events', # "changing pi"
             'http://frontbed5:9059/graph/events', #  "frontbed pi"
             'http://workshop5:9059/graph/events',
             'http://bang:9075/graph/events', # "env"
             'http://bang:9070/graph/events', # "wifi usage"
             #'http://bang:9099/graph/events', # "trails" (big!)
             'http://dash:9095/graph/dpms/events', # "dash monitor"
             'http://dash:9107/graph/xidle/events', # "dash x idle"
             #'http://slash:9095/graph/dpms/events', # "slash monitor"
             #'http://slash:9107/graph/xidle/events', # "slash x idle"
             'http://frontdoor5:9059/graph/events', # frontdoor pi
             'http://frontdoor5:9095/graph/dpms/events', #  "frontdoor monitor"
             'http://frontdoor5:9107/graph/xidle/events', #  "frontdoor x idle"
             'http://frontdoor5:10012/graph/events', #  "frontdoor rfid"
             'http://frontdoor5:10013/graph/events', #  "frontdoor tiny screen"

             'http://bang:10018/mqtt/events', #  "frontwindow tag reader"
             'http://bang:10011/graph/events', #  "frontdoor lock"
             'http://bang:10006/timebank/events',
             'http://bang:10016/power/events',
             'http://bang:10015/store/events', # store
             'http://bang:10018/mqtt/events', # rdf_from_mqtt
         ]},
        {'id': 'frontDoor',
         'sources': [
             'http://bang:10006/timebank/events',
             'http://bang:10015/store/events',
             'http://bang:10016/power/events',
             'http://bang:10018/graph/events', #  "frontwindow tag reader"
             'http://bang:10018/mqtt/events', # rdf_from_mqtt
             'http://bang:9059/graph/events', # "bang arduino"
             'http://bang:9075/graph/events', # "env"
             'http://bang:9105/countdownGraph/events',
             'http://bang:9105/graph/events', # calendar
             'http://frontbed5:9059/graph/events',
             'http://garage5:9059/graph/events',
             'http://kitchen5:9059/graph/events',
             'http://living5:9059/graph/events',
             'http://workshop5:9059/graph/events',
         ]},
        {'id': 'network',
         'sources': [
             'http://bang:9070/graph/events', # "wifi usage"
             'http://bang:9073/graph/events', # "dhcpd"
             'http://bang:9009/graph/traffic/events', # 10.2 traffic
         ]},
        {'id': 'source_frontDoor',
         'sources': [
             'http://frontdoor5:9059/graph/events', # frontdoor pi
             'http://frontdoor5:9095/graph/dpms/events', #  "frontdoor monitor"
             'http://frontdoor5:9107/graph/xidle/events', #  "frontdoor x idle"
             'http://frontdoor5:10012/graph/events', #  "frontdoor rfid"
             'http://frontdoor5:10013/graph/events', #  "frontdoor tiny screen"
             'http://bang:10011/graph/events', #  "frontdoor lock"
             'http://bang:10018/graph/events', #  "frontwindow tag reader"
         ]},
        {'id': 'env',
         'sources': [
             'http://bang:9075/graph/events', # "env"
         ]},
        {'id': 'workshop',
         'sources': [
             'http://workshop5:9059/graph/events',
         ]},

    ]
}
