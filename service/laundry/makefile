
run: laundry
	./laundry

laundry: laundry.go
	GOPATH=`pwd` /opt/go/bin/go build laundry.go

deps:
	GOPATH=`pwd` /opt/go/bin/go get github.com/mrmorphic/hwio
	GOPATH=`pwd` /opt/go/bin/go get github.com/stretchr/goweb
	apt-get install libraptor2-dev
	GOPATH=`pwd` /opt/go/bin/go get bitbucket.org/ww/goraptor
	perl -lpi -e 's,/usr/local/,/usr/,' src/bitbucket.org/ww/goraptor/goraptor.go
	GOPATH=`pwd` /opt/go/bin/go build .../goraptor
