config = {
    'streams': [
        {'id': 'home',
         'sources': [
             # should be from :reasoning :source ?s
             'http://garage.vpn-home:9059/graph/events', # "garage pi"
             'http://kitchen.vpn-home:9059/graph/events', # "kitchen pi"
             'http://living.vpn-home:9059/graph/events', # "living room pi"
             'http://bang:9059/graph/events', # "bang arduino"
             'http://bed.vpn-home:9059/graph/events', # "bed pi"
             'http://changing.vpn-home:9059/graph/events', # "changing pi"
             'http://frontbed.vpn-home:9059/graph/events', #  "frontbed pi"
             'http://workshop.vpn-home:9059/graph/events', 
             'http://bang:9075/graph/events', # "env"
             'http://bang:9070/graph/events', # "wifi usage"
             #'http://bang:9099/graph/events', # "trails" (big!)
             'http://dash:9095/graph/events', # "dash monitor"
             'http://dash:9107/graph/events', # "dash x idle"
             #'http://slash:9095/graph/events', # "slash monitor"
             #'http://slash:9107/graph/events', # "slash x idle"
             'http://frontdoor.vpn-home:9059/graph/events', # frontdoor pi
             'http://frontdoor.vpn-home:9095/graph/events', #  "frontdoor monitor" 
             'http://frontdoor.vpn-home:9107/graph/events', #  "frontdoor x idle"
             'http://frontdoor.vpn-home:10012/graph/events', #  "frontdoor rfid"
             'http://frontdoor.vpn-home:10013/graph/events', #  "frontdoor tiny screen"
             'http://bang:10011/graph/events', #  "frontdoor lock"
             'http://bang:10008/graph/events', # kitchen H801
             'http://bang:10015/graph/events', # store
         ]},
        {'id': 'frontDoor',
         'sources': [
             'http://garage.vpn-home:9059/graph/events', 
             'http://kitchen.vpn-home:9059/graph/events',
             'http://living.vpn-home:9059/graph/events', 
             'http://workshop.vpn-home:9059/graph/events', 
             'http://bang.vpn-home:9105/graph/events', # calendar
             'http://bang.vpn-home:9059/graph/events', # "bang arduino"
             'http://frontbed.vpn-home:9059/graph/events', 
             'http://bang:10015/graph/events', # store
             ]},
        {'id': 'network',
         'sources': [
             'http://bang:9070/graph/events', # "wifi usage"
             'http://bang:9073/graph/events', # "dhcpd"
         ]},
        {'id': 'source_frontDoor',
         'sources': [
             'http://frontdoor.vpn-home:9059/graph/events', # frontdoor pi
             'http://frontdoor.vpn-home:9095/graph/events', #  "frontdoor monitor" 
             'http://frontdoor.vpn-home:9107/graph/events', #  "frontdoor x idle"
             'http://frontdoor.vpn-home:10012/graph/events', #  "frontdoor rfid"
             'http://frontdoor.vpn-home:10013/graph/events', #  "frontdoor tiny screen"
             'http://bang:10011/graph/events', #  "frontdoor lock"
         ]},
        {'id': 'env',
         'sources': [
             'http://bang:9075/graph/events', # "env"
         ]},
        {'id': 'workshop',
         'sources': [
             'http://workshop.vpn-home:9059/graph/events', 
         ]},
        
    ]
}
