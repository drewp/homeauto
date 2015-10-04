reconnectingWebSocket = (url, onMessage) ->
  connect = ->
    ws = new WebSocket(url)
    ws.onopen = ->
      $("#status").text "connected"

    ws.onerror = (e) ->
      $("#status").text "error: " + e

    ws.onclose = ->
      pong = 1 - pong
      $("#status").text "disconnected (retrying " + ((if pong then "<U+1F63C>" else "<U+1F63A>")) + ")"
      
      # this should be under a requestAnimationFrame to
      # save resources
      setTimeout connect, 2000

    ws.onmessage = (evt) ->
      onMessage JSON.parse(evt.data)
  pong = 0
  connect()


model =
  imageIndex: ko.observable(-1)
  feederCam: ko.observable(false)

model.toggleFeederCam = ->
    if model.feederCam()
      $("#feeder").empty().hide()
      model.feederCam(false)
    else
      $("#feeder").append($("<img>").attr("src", "http://bang.bigasterisk.com/ipcam1/videostream.cgi?rate=6")).show()
      model.feederCam(true)

images = [
  '../images/3387331383_d5c530cd9e_z.jpg',
  '../images/1878786955_1356972060.jpg',
  '../images/cactus_3731166_lrg.jpg',
  '../images/cactus-header-1024x683.jpg',
  '../images/cactus.jpg',
  '../images/Nopal-cactus.jpg',
  '../images/round-cactus.jpg',
  '../images/Singapore_Botanic_Gardens_Cactus_Garden_2.jpg',
  '../images/f10.jpg',
  '../images/f11.jpg',
  '../images/f12.jpg',
  '../images/f13.jpg',
  '../images/f1.jpg',
  '../images/f2.jpg',
  '../images/f3.jpg',
  '../images/f4.jpg',
  '../images/f5.jpg',
  '../images/f6.jpg',
  '../images/f7.jpg',
  '../images/f8.jpg',
  '../images/f9.jpg',
]

model.nextImage = ->
  model.imageIndex((model.imageIndex() + 1) % images.length)
  $("#main").attr('src', images[model.imageIndex()])
model.nextImage()  

reconnectingWebSocket("ws://bang:9071/events", (msg) ->
  console.log("got", msg)
  if msg.o == "http://bigasterisk.com/host/star/slideshow/advance"
    model.nextImage()
  if msg.o == "http://bigasterisk.com/host/star/slideshow/toggleFeeder"
    model.toggleFeederCam()
)
ko.applyBindings(model)
