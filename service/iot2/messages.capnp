@0x884608a79526d38a;

# Can't use Text type; nim doesn't support it. The Data type becomes nim 'string'.

struct Report {
  sensor @0 :Data;
  value @1 :Float32;
}

# node is at config version n (config pusher will update it)
# replace node config
# node component returns interesting sensor reports
# node component periodically returns state
# send 'command' updates to components

# from node: <node>/announce
# (<node> is picked by the node itself, often hostname or an id compiled into esp code)
struct NodeAnnounce {
  config_version @0 :Int32;
  hostname @1 :Data;
  mac_address @2 :UInt64; # 48-bit
}

# to node: <node>/configure
struct ConfigureNode {
  config_version @0 :Int32;
  components @0 :List(Component)
  struct Component {
    id :Text

  }
}
