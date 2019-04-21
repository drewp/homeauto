import asynchttpserver, asyncdispatch, asyncnet, strtabs, sequtils, times, os, strutils, strformat
import sets
import rdf
import rdf_nodes

type
  GraphServer* = ref object of RootObj
    port*: int
    clients: seq[AsyncSocket]
    previousUpdateTime: int
    httpServer: AsyncHttpServer
    serverReady: Future[void]
    graph: Graph

proc ssePayload(eventType: string, body: string): string =
  eventType & ": " & body & "\n\n"
  
proc sendEvent(client: AsyncSocket, eventType: string, body: string) {.async.} =
  if not client.isClosed():
    asyncCheck client.send(ssePayload(eventType, body))
  
proc sendEventToAll(self: GraphServer, eventType: string, body: string) {.async.} =
  let payload = ssePayload(eventType, body)
  for client in self.clients:
    if not client.isClosed():
      asyncCheck client.send(payload)
    
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
  await sendEvent(req.client, "fullGraph", Patch(addQuads: self.graph.stmts).toJson())
  self.clients.add(req.client)

proc handleConnections(self: GraphServer, req: Request) {.async.} =
  let clientCount = self.clients.len
  let headers = newHttpHeaders({"Content-Type": "text/plain",
                                "Access-Control-Allow-Origin": "*",
                                "Cache-Control": "no-cache",
                                "Connection": "close"})

  await req.respond(Http200, $clientCount, headers)
  req.client.close()

proc handleGraph(self: GraphServer, req: Request) {.async.} =
  await req.respond(Http200, self.graph.toNquads(), newHttpHeaders({
    "Content-Type": "application/n-quads",
    }))
  req.client.close()
  
proc applyPatch*(self: GraphServer, p: Patch) {.async.} =
  self.graph.applyPatch(p)
  let body = p.toJson()
  echo "emitpatch " & body
  asyncCheck self.sendEventToAll("patch", body)

# Replace graph contents. 
proc setGraph*(self: GraphServer, quads: HashSet[Quad]) {.async.} =
  let p = Patch(addQuads: quads - self.graph.stmts,
                delQuads: self.graph.stmts - quads)
  asyncCheck self.graph.applyPatch(p)

proc handleCurrentGraph(self: GraphServer, req: Request) {.async.} =
  let quad = HashSet[Quad]([])
  self.setGraph(quads)


proc requestCallback(self: GraphServer, req: Request) {.async.} =
  if req.reqMethod == HttpOptions:
    asyncCheck handleCORS(req)
  else:
    case req.url.path
    of "/connections": asyncCheck self.handleConnections(req)
    of "/graph": asyncCheck self.handleGraph(req)
    of "/graph/events": asyncCheck self.handleSSE(req)
    of "/currentGraph": asyncCheck self.handleCurrentGraph(req)
    else: asyncCheck handle404(req)

proc newGraphServer*(port: int): GraphServer =
  new(result)
  result.port = port
  result.previousUpdateTime = toInt(epochTime() * 1000)
  result.graph = initGraph()

  result.httpServer = newAsyncHttpServer(true)
  let self = result
  # https://github.com/dom96/nim-in-action-code/issues/6#issuecomment-446956468 has been applied to ./nim-0.19.4/lib/pure/asynchttpserver.nim
  proc handler(req: Request): Future[void] {.async.} =
    asyncCheck self.requestCallback(req)
  self.serverReady = self.httpServer.serve(Port(self.port), handler, address="0.0.0.0")
  asyncCheck self.serverReady
  echo "Listening on " & $self.port
  

proc checkClients(self: GraphServer) =
  self.clients = self.clients.filterIt(not it.isClosed())

proc pingClients(self: GraphServer) {.async.} =
  let currentTime = toInt(epochTime() * 1000)

  if currentTime - self.previousUpdateTime < 1000:
    return

  asyncCheck self.sendEventToAll("data", $currentTime)
  self.previousUpdateTime = toInt(epochTime() * 1000)

  
proc run*(self: GraphServer) =
  while true:
    self.checkClients()
    asyncCheck self.pingClients()
    poll()

   

let server = newGraphServer(port = 10012)
server.run()