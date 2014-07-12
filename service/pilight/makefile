GOPATH=$(shell pwd)
export GOPATH
build:
	go build pilight.go

setup:
	go get github.com/tarm/goserial
	go get github.com/go-martini/martini
	ln -s . public
	# also need static/polymer/ to be polymer 0.2.3

