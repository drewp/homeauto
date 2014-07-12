GOPATH=$(shell pwd)
export GOPATH
build: deps
	go build pilight.go

deps: src/github.com/tarm/goserial src/github.com/go-martini/martini

src/github.com/tarm/goserial:
	go get github.com/tarm/goserial
src/github.com/go-martini/martini:
	go get github.com/go-martini/martini

setup:
	ln -s . public
	@echo also need static/polymer/ to be polymer 0.2.3

build-to-pi: deps
	GOBIN=bin-pi GOARCH=arm go install pilight.go
	rsync -a bin-pi/pilight pi@192.168.1.157:projects/homeauto/service/pilight/bin/
