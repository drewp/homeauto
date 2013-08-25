
run: laundry
	./laundry

laundry: laundry.go
	GOPATH=`pwd` /opt/go/bin/go build laundry.go

deps:
	GOPATH=`pwd` /opt/go/bin/go get github.com/mrmorphic/hwio
	GOPATH=`pwd` /opt/go/bin/go get github.com/bmizerany/pat
