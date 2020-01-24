@0x884608a79526d38a;

# Can't use Text type; nim doesn't support it. The Data type becomes nim 'string'.

struct Report {
  sensor @0 :Data;
  value @1 :Float32;
}
