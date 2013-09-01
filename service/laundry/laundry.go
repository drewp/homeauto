package main

import (
	"bitbucket.org/ww/goraptor"
	"encoding/json"
	"errors"
	"github.com/mrmorphic/hwio"
	"github.com/stretchr/goweb"
	"github.com/stretchr/goweb/context"
	"log"
	"net"
	"net/http"
	"runtime"
	"time"
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
	LastOutLed, LastOutStrike                                                              string
}

func DigitalRead(p hwio.Pin) int {
	v, err := hwio.DigitalRead(p)
	if err != nil {
		panic(err)
	}
	return v
}

func (h *Hardware) GetMotion() string {
	if DigitalRead(h.InMotion) == 0 {
		return "motion"
	} else {
		return "noMotion"
	}
}

func (h *Hardware) GetDoor() string {
	if DigitalRead(h.InDoorClosed) == 1 {
		return "closed"
	} else {
		return "open"
	}
}

func (h *Hardware) GetSwitch(which string) string {
	var level int
	switch which {
	case "1":
		level = DigitalRead(h.InSwitch1)
	case "2":
		level = DigitalRead(h.InSwitch2)
	case "3":
		level = DigitalRead(h.InSwitch3)
	}
	if level == 0 {
		return "closed"
	} else {
		return "open"
	}
}

func (h *Hardware) GetLed() string {
	return h.LastOutLed
}

func (h *Hardware) GetStrike() string {
	return h.LastOutStrike
}

func (h *Hardware) SetLed(state string) {
	switch state {
	case "on":
		hwio.DigitalWrite(h.OutLed, 1)
	case "off":
		hwio.DigitalWrite(h.OutLed, 0)
	default:
		panic(errors.New("unknown state"))
	}
	h.LastOutLed = state
}

func (h *Hardware) SetStrike(state string) {
	switch state {
	case "unlocked":
		hwio.DigitalWrite(h.OutStrike, 1)
	case "locked":
		hwio.DigitalWrite(h.OutStrike, 0)
	default:
		panic(errors.New("unknown state"))
	}
	h.LastOutStrike = state
}

// hwio.GetPin with a panic instead of an error return
func GetPin(id string) hwio.Pin {
	p, e := hwio.GetPin(id)
	if e != nil {
		panic(e)
	}
	return p
}

func SetupIo() Hardware {
	//	return Hardware{}
	pins := Hardware{
		InMotion:     GetPin("GPIO2"), // pi rev2 calls it GPIO2
		InSwitch3:    GetPin("GPIO3"), // pi rev2 calls it GPIO3
		InSwitch1:    GetPin("GPIO4"),
		InSwitch2:    GetPin("GPIO17"),
		OutLed:       GetPin("GPIO27"), // pi rev2 calls it GPIO27
		OutSpeaker:   GetPin("GPIO22"),
		InDoorClosed: GetPin("GPIO10"),
		OutStrike:    GetPin("GPIO9"),
	}

	if err := hwio.PinMode(pins.InMotion, hwio.INPUT_PULLUP); err != nil {
		panic(err)
	}
	if err := hwio.PinMode(pins.InSwitch1, hwio.INPUT_PULLUP); err != nil {
		panic(err)
	}
	if err := hwio.PinMode(pins.InSwitch2, hwio.INPUT_PULLUP); err != nil {
		panic(err)
	}
	if err := hwio.PinMode(pins.InSwitch3, hwio.INPUT_PULLUP); err != nil {
		panic(err)
	}
	if err := hwio.PinMode(pins.InDoorClosed, hwio.INPUT_PULLDOWN); err != nil {
		panic(err)
	}
	if err := hwio.PinMode(pins.OutLed, hwio.OUTPUT); err != nil {
		panic(err)
	}
	if err := hwio.PinMode(pins.OutSpeaker, hwio.OUTPUT); err != nil {
		panic(err)
	}
	if err := hwio.PinMode(pins.OutStrike, hwio.OUTPUT); err != nil {
		panic(err)
	}
	pins.SetLed("off")
	pins.SetStrike("locked")
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
		panic(err)
	}
	c.HttpResponseWriter().Header().Set("Content-Type",
		goraptor.SerializerSyntax[syntaxName].MimeType)
	return goweb.Respond.With(c, 200, []byte(str))
}

func namespace(ns string) func(string) *goraptor.Uri {
	return func(path string) *goraptor.Uri {
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

func main() {
	pins := SetupIo()

	goweb.MapStatic("/static", "static")

	// this one needs to fail if the hardware is broken in
	// any way that we can determine, though I'm not sure
	// what that will mean on rpi
	goweb.MapStaticFile("/", "index.html")

	goweb.Map("GET", "/status", func(c context.Context) error {
		jsonEncode := json.NewEncoder(c.HttpResponseWriter())
		jsonEncode.Encode(map[string]interface{}{
			"motion":     pins.GetMotion(),
			"switch1":    pins.GetSwitch("1"),
			"switch2":    pins.GetSwitch("2"),
			"switch3":    pins.GetSwitch("3"),
			"doorClosed": pins.GetDoor(),
			"led":        pins.LastOutLed,
			"strike":     pins.LastOutStrike,
		})
		return nil
	})

	goweb.Map("GET", "/trig", func(c context.Context) error {
		DC := namespace("http://purl.org/dc/terms/")
		ROOM := namespace("http://projects.bigasterisk.com/room/")
		statements := make(chan *goraptor.Statement, 100)
		graph := ROOM("laundryDoor")
		statements <- &(goraptor.Statement{
			graph, DC("modified"), nowLiteral(), graph})
		
		close(statements)
		return serializeGowebResponse(c, "trig", statements)
	})
		
	goweb.Map("GET", "/graph", func(c context.Context) error {
		DC := namespace("http://purl.org/dc/terms/")
		ROOM := namespace("http://projects.bigasterisk.com/room/")

		statements := make(chan *goraptor.Statement, 100)

		graph := ROOM("laundryDoor")

		_, thisFile, _, _ := runtime.Caller(0)
		statements <- &(goraptor.Statement{
			graph, DC("creator"), literal(thisFile, nil), graph})
		statements <- &(goraptor.Statement{
			graph, DC("modified"), nowLiteral(), graph})

		for subj, state := range map[*goraptor.Uri]*goraptor.Uri{
			ROOM("laundryDoorMotion"):  ROOM(pins.GetMotion()),
			ROOM("laundryDoorOpen"):    ROOM(pins.GetDoor()),
			ROOM("laundryDoorSwitch1"): ROOM(pins.GetSwitch("1")),
			ROOM("laundryDoorSwitch2"): ROOM(pins.GetSwitch("2")),
			ROOM("laundryDoorSwitch3"): ROOM(pins.GetSwitch("3")),
			ROOM("laundryDoorLed"):     ROOM(pins.GetLed()),
			ROOM("laundryDoorStrike"):  ROOM(pins.GetStrike()),
		} {
			statements <- &(goraptor.Statement{subj, ROOM("state"), state, graph})
		}

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

		pins.SetLed(string(body))
		return goweb.Respond.WithStatusText(c, http.StatusAccepted)
	})

	goweb.Map("PUT", "/strike", func(c context.Context) error {
		body, err := c.RequestBody()
		if err != nil {
			panic(err)
		}

		pins.SetStrike(string(body))
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
			pins.SetStrike("unlocked")
			go func() {
				time.Sleep(time.Duration(req.Seconds *
					float64(time.Second)))
				pins.SetStrike("locked")
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
		Addr:         address,
		Handler:      goweb.DefaultHttpHandler(),
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
	}

	log.Printf("Listening on port %s", address)
	log.Printf("%s", goweb.DefaultHttpHandler())
	listener, listenErr := net.Listen("tcp", address)
	if listenErr != nil {
		panic(listenErr)
	}
	s.Serve(listener)
}
