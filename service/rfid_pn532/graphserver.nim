import asynchttpserver, asyncdispatch, asyncnet, strtabs, sequtils, times, os, strutils, strformat

type
  GraphServer* = ref object of RootObj
    port*: int
    clients: seq[AsyncSocket]
    previousUpdateTime: int
    httpServer: AsyncHttpServer
    serverReady: Future[void]
    
proc handleCORS(req: Request) {.async.} =
  await req.respond(Http204, "", newHttpHeaders({
    "Access-Control-Allow-Origin": "*",
    "Connection": "close"}))

proc handle404(req: Request) {.async.} =
  let headers = newHttpHeaders({"Content-Type": "text/plain",
                                "Connection": "close"})

  await req.respond(Http404, "File not found", headers)
  req.client.close()

proc handleSSE(self: GraphServer, req: Request) {.async.} =
  let headers = newHttpHeaders({"Content-Type": "text/event-stream",
                                "Access-Control-Allow-Origin": "*",
                                "Cache-Control": "no-cache",
                                "Connection": "keep-alive"})

  await req.client.send("HTTP/1.1 200 OK\c\L")
  await req.sendHeaders(headers)
  await req.client.send("\c\L:ok\n\n")
  self.clients.add(req.client)

proc handleConnections(self: GraphServer, req: Request) {.async.} =
  let clientCount = self.clients.len
  let headers = newHttpHeaders({"Content-Type": "text/plain",
                                "Access-Control-Allow-Origin": "*",
                                "Cache-Control": "no-cache",
                                "Connection": "close"})

  await req.respond(Http200, $clientCount, headers)
  req.client.close()

proc requestCallback(self: GraphServer, req: Request) {.async.} =
  if req.reqMethod == HttpOptions:
    asyncCheck handleCORS(req)
  else:
    case req.url.path
    of "/connections": asyncCheck self.handleConnections(req)
    of "/sse": asyncCheck self.handleSSE(req)
    else: asyncCheck handle404(req)

proc newGraphServer*(port: int): GraphServer =
  new(result)
  result.port = port
  result.previousUpdateTime = toInt(epochTime() * 1000)

  result.httpServer = newAsyncHttpServer(true)
  let self = result
  self.serverReady = self.httpServer.serve(
    Port(self.port),
    proc (req: Request): Future[void] = self.requestCallback(req),
    address="0.0.0.0")
  asyncCheck self.serverReady
  echo "Listening on " & $self.port
  

proc checkClients(self: GraphServer) =
  self.clients = self.clients.filterIt(not it.isClosed())

proc pingClients(self: GraphServer) {.async.} =
  let currentTime = toInt(epochTime() * 1000)

  if currentTime - self.previousUpdateTime < 1000:
    return

  for client in self.clients:
    if not client.isClosed():
      asyncCheck client.send("data: " & $currentTime & "\n\n")

  self.previousUpdateTime = toInt(epochTime() * 1000)

proc run*(self: GraphServer) =
  while true:
    self.checkClients()
    asyncCheck self.pingClients()
    poll()


