import threadpool

var events1: Channel[int]
events1.send(1)

proc main():
  var events2: Channel[int]
  events2.send(2)

main()
