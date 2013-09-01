package main

import (
	"encoding/json"
	"log"
	"net"
	"net/http"
	"strconv"
	"fmt"
	"time"
	"runtime"
	"github.com/mrmorphic/hwio"
	"github.com/stretchr/goweb"
	"github.com/stretchr/goweb/context"
	"bitbucket.org/ww/goraptor"
)

/*
hwio.DebugPinMap() wrote this:

Pin 1: 3.3V,  cap:
Pin 2: 5V,  cap:
Pin 3: SDA,GPIO0  cap:output,input,input_pullup,input_pulldown
Pin 5: SCL,GPIO1  cap:output,input,input_pullup,input_pulldown
Pin 6: GROUND,  cap:
Pin 7: GPIO4  cap:output,input,input_pullup,input_pulldown
Pin 8: TXD,GPIO14  cap:output,input,input_pullup,input_pulldown
Pin 10: RXD,GPIO15  cap:output,input,input_pullup,input_pulldown
Pin 11: GPIO17  cap:output,input,input_pullup,input_pulldown
Pin 12: GPIO18  cap:output,input,input_pullup,input_pulldown
Pin 13: GPIO21  cap:output,input,input_pullup,input_pulldown
Pin 15: GPIO22  cap:output,input,input_pullup,input_pulldown
Pin 16: GPIO23  cap:output,input,input_pullup,input_pulldown
Pin 18: GPIO24  cap:output,input,input_pullup,input_pulldown
Pin 19: MOSI,GPIO10  cap:output,input,input_pullup,input_pulldown
Pin 21: MISO,GPIO9  cap:output,input,input_pullup,input_pulldown
Pin 22: GPIO25  cap:output,input,input_pullup,input_pulldown
Pin 23: SCLK,GPIO11  cap:output,input,input_pullup,input_pulldown
Pin 24: CE0N,GPIO8  cap:output,input,input_pullup,input_pulldown
Pin 26: CE1N,GPIO7  cap:output,input,input_pullup,input_pulldown
*/

type Hardware struct {
	InMotion, InSwitch3, InSwitch1, InSwitch2, OutLed, OutSpeaker, InDoorClosed, OutStrike hwio.Pin
	LastOutLed, LastOutStrike int
}

// hwio.GetPin with a panic instead of an error return
func GetPin(id string) hwio.Pin {
	p, e := hwio.GetPin(id)
	if e != nil {
		panic(e)
	}
	return p
}

func DigitalRead(p hwio.Pin) int {
	v, err := hwio.DigitalRead(p)
	if err != nil {
		panic(err)
	}
	return v
}

func SetupIo() Hardware {
//	return Hardware{}
	pins := Hardware{
		InMotion:		GetPin("GPIO2"), // pi rev2 calls it GPIO2
		InSwitch3:		GetPin("GPIO3"), // pi rev2 calls it GPIO3
		InSwitch1:		GetPin("GPIO4"),
		InSwitch2:		GetPin("GPIO17"),
		OutLed:			GetPin("GPIO27"), // pi rev2 calls it GPIO27
		OutSpeaker:		GetPin("GPIO22"),
		InDoorClosed:	GetPin("GPIO10"),
		OutStrike:      GetPin("GPIO9"),
	}
	
	if err := hwio.PinMode(pins.InMotion,	  hwio.INPUT_PULLUP); err != nil { panic(err) }
	if err := hwio.PinMode(pins.InSwitch1,	  hwio.INPUT_PULLUP); err != nil { panic(err) }
	if err := hwio.PinMode(pins.InSwitch2,	  hwio.INPUT_PULLUP); err != nil { panic(err) }
	if err := hwio.PinMode(pins.InSwitch3,	  hwio.INPUT_PULLUP); err != nil { panic(err) }
	if err := hwio.PinMode(pins.InDoorClosed, hwio.INPUT_PULLUP); err != nil { panic(err) }
	if err := hwio.PinMode(pins.OutLed,       hwio.OUTPUT); err != nil { panic(err) }
	if err := hwio.PinMode(pins.OutSpeaker,	  hwio.OUTPUT); err != nil { panic(err) }
	if err := hwio.PinMode(pins.OutStrike,	  hwio.OUTPUT); err != nil { panic(err) }
	return pins
}

func serializeGowebResponse(
	c context.Context,
	syntaxName string,
	statements chan *goraptor.Statement) error {
	serializer := goraptor.NewSerializer(syntaxName)
	defer serializer.Free()

	str, err := serializer.Serialize(statements, "")
	if err != nil {
		panic(err);
	}
	c.HttpResponseWriter().Header().Set("Content-Type",
		goraptor.SerializerSyntax[syntaxName].MimeType)
	return goweb.Respond.With(c, 200, []byte(str))
}

func namespace(ns string) (func(string) *goraptor.Uri) {
	return func (path string) *goraptor.Uri {
		var u goraptor.Uri = goraptor.Uri(ns + path)
		return &u
	}
}

func literal(v string, datatype *goraptor.Uri) (ret *goraptor.Literal) {
	ret = new(goraptor.Literal)
	ret.Value = v
	if datatype != nil {
		ret.Datatype = string(*datatype)
	}
	return
}

func nowLiteral() *goraptor.Literal {
	XS := namespace("http://www.w3.org/2001/XMLSchema#")
	rfc3999Time, err := time.Now().MarshalJSON()
	if err != nil {
		panic(err)
	}
	return literal(string(rfc3999Time[:]), XS("dateTime"))
}

func twoState(
	graph *goraptor.Uri,
	subject *goraptor.Uri,
	test interface{},
	trueVal interface{}, trueObject *goraptor.Uri,
	falseVal interface{}, falseObject *goraptor.Uri,
) *goraptor.Statement {
	ROOM := namespace("http://projects.bigasterisk.com/room/")
	var motionState goraptor.Term
	if test == trueVal {
		motionState = trueObject
	} else if test == falseVal {
		motionState = falseObject
	} else {
		motionState = literal(fmt.Sprintf("%v", test), nil)
	}
	return &(goraptor.Statement{
		subject, ROOM("state"), motionState, graph})
}

func main() {
	pins := SetupIo()

	goweb.MapStatic("/static", "static")

	// this one needs to fail if the hardware is broken in
	// any way that we can determine, though I'm not sure
	// what that will mean on rpi
	goweb.MapStaticFile("/", "index.html")
	
	goweb.Map("GET", "/status", func(c context.Context) error {
		jsonEncode := json.NewEncoder(c.HttpResponseWriter())
		jsonEncode.Encode(map[string]int{
			"motion": DigitalRead(pins.InMotion),
			"switch1": DigitalRead(pins.InSwitch1),
			"switch2": DigitalRead(pins.InSwitch2),
			"switch3": DigitalRead(pins.InSwitch3),
			"doorClosed": DigitalRead(pins.InDoorClosed),
			"led": pins.LastOutLed,
			"strike": pins.LastOutStrike,
		})
		return nil
	})

	goweb.Map("GET", "/graph", func(c context.Context) error {
		DC := namespace("http://purl.org/dc/terms/")
		ROOM := namespace("http://projects.bigasterisk.com/room/")

		statements := make(chan *goraptor.Statement, 100)

		graph := ROOM("laundrySensors")

		_, thisFile, _, _ := runtime.Caller(0)
		statements <- &(goraptor.Statement{
			graph, DC("creator"), literal(thisFile, nil), graph})
		statements <- &(goraptor.Statement{
			graph, DC("modified"), nowLiteral(), graph})

		statements <- twoState(graph, ROOM("laundryDoorMotion"),
			DigitalRead(pins.InMotion),
			1, ROOM("motion"),
			0, ROOM("noMotion"))

		statements <- twoState(graph, ROOM("laundryDoorOpen"),
			DigitalRead(pins.InDoorClosed),
			1, ROOM("closed"),
			0, ROOM("open"))

		for i, p := range map[string]hwio.Pin{
			"1": pins.InSwitch1,
			"2": pins.InSwitch2,
			"3": pins.InSwitch3} {
			statements <- twoState(
				graph, ROOM("laundryDoorSwitch" + i),
				DigitalRead(p),
				1, ROOM("closed"),
				0, ROOM("open"))
		}

		statements <- twoState(graph, ROOM("laundryDoorLed"),
			pins.LastOutLed, 1, ROOM("on"), 0, ROOM("off"))
		
		statements <- twoState(graph, ROOM("laundryDoorStrike"),
			pins.LastOutLed, 1, ROOM("unlocked"), 0, ROOM("locked"))
		
		close(statements)
		// type should be chosen with accept header. trig is
		// causing segfaults.
		return serializeGowebResponse(c, "nquads", statements)
	})

	goweb.Map("PUT", "/led", func(c context.Context) error {
		body, err := c.RequestBody()
		if err != nil {
			panic(err)
		}
		
		var level int
		if string(body) == "on" {
			level = 1
		} else if string(body) == "off" {
			level = 0
		} else {
			return goweb.Respond.With(c, http.StatusBadRequest,
				[]byte("body must be 'on' or 'off'"))
		}

		hwio.DigitalWrite(pins.OutLed, level)
		pins.LastOutLed = level
		return goweb.Respond.WithStatusText(c, http.StatusAccepted)
	})

	setStrike := func (level int) {
		hwio.DigitalWrite(pins.OutStrike, level)
		pins.LastOutStrike = level
	}
	
	goweb.Map("PUT", "/strike", func(c context.Context) error {
		body, err := c.RequestBody()
		if err != nil {
			panic(err)
		}

		level, err := strconv.Atoi(string(body[:]))
		if err != nil {
			return goweb.Respond.With(c, http.StatusBadRequest,
				[]byte("body must be '0' or '1'"))
		}

		setStrike(level)
		return goweb.Respond.WithStatusText(c, http.StatusAccepted)
	})
	
	goweb.Map(
		"PUT", "/strike/temporaryUnlock",
		func(c context.Context) error {
			type TemporaryUnlockRequest struct {
				Seconds float64
			}

			var req TemporaryUnlockRequest
			err := json.NewDecoder(c.HttpRequest().Body).
				Decode(&req)
			if err != nil {
				panic(err)
			}

			// This is not correctly reentrant. There should be a
			// stack of temporary effects that unpop correctly,
			// and status should show you any running effects.
			setStrike(1)
			go func() {
				time.Sleep(time.Duration(req.Seconds *
					float64(time.Second)))
				setStrike(0)
			}()
			return goweb.Respond.WithStatusText(
				c, http.StatusAccepted)
		})

	goweb.Map("PUT", "/speaker/beep", func(c context.Context) error {
		// queue a beep
		return goweb.Respond.WithStatusText(c, http.StatusAccepted)
	})


	address := ":8081"
	
	s := &http.Server{
		Addr:           address,
		Handler:        goweb.DefaultHttpHandler(),
		ReadTimeout:    10 * time.Second,
		WriteTimeout:   10 * time.Second,
	}

	log.Printf("Listening on port %s", address)
	log.Printf("%s", goweb.DefaultHttpHandler())
	listener, listenErr := net.Listen("tcp", address)
	if listenErr != nil {
		panic(listenErr)
	}
	s.Serve(listener)
}
