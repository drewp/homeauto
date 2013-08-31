package main

import (
	"io/ioutil"
	"log"
	"net/http"
	"strconv"
	"time"
	"net"
	"os"
	"encoding/json"
	"os/signal"
	"github.com/mrmorphic/hwio"
	"github.com/stretchr/goweb"
	"github.com/stretchr/goweb/context"
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

type Pins struct {
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

func SetupIo() Pins {
	pins := Pins{
		InMotion:		GetPin("GPIO0"),
		InSwitch3:		GetPin("GPIO1"),
		InSwitch1:		GetPin("GPIO4"),
		InSwitch2:		GetPin("GPIO17"),
		OutLed:			GetPin("GPIO21"),
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
	

func booleanBody(w http.ResponseWriter, r *http.Request) (level int, err error) {
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		panic(err)
	}
	level, err2 := strconv.Atoi(string(body[:]))
	if err2 != nil {
		http.Error(w, "body must be '0' or '1'", http.StatusBadRequest)
		return 0, err
	}
	return level, nil
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

	/*
	m.Put("/led", http.HandlerFunc(func (w http.ResponseWriter, r *http.Request) {
		body, err := ioutil.ReadAll(r.Body)
		if err != nil {
			panic(err)
		}
		var level int
		if string(body) == "on" {
			level = 1
		} else if string(body) == "off" {
			level = 0
		} else {
			http.Error(w, "body must be 'on' or 'off'", http.StatusBadRequest)
			return 
		}

		hwio.DigitalWrite(pins.OutLed, level)
		pins.LastOutLed = level
		http.Error(w, "", http.StatusAccepted)
	}))

	setStrike := func (level int) {
		hwio.DigitalWrite(pins.OutStrike, level)
		pins.LastOutStrike = level
	}
	
	m.Put("/strike", http.HandlerFunc(func (w http.ResponseWriter, r *http.Request) {
		level, err := booleanBody(w, r)
		if err != nil {
			panic(err)
		}
		setStrike(level)
		http.Error(w, "", http.StatusAccepted)
	}))
	
	m.Put("/strike/temporaryUnlock", http.HandlerFunc(func (w http.ResponseWriter, r *http.Request) {
		err := r.ParseForm()
		if err != nil {
			panic(err)
		}
		seconds, err2 := strconv.ParseFloat(string(r.Form["seconds"][0]), 32)
		if err2 != nil {
			http.Error(w, "seconds must be a float", http.StatusBadRequest)
			return
		}

		// This is not correctly reentrant. There should be a
		// stack of temporary effects that unpop correctly,
		// and status should show you any running effects.
		setStrike(1)
		go func() {
			time.Sleep(time.Duration(seconds * float64(time.Second)))
			setStrike(0)
		}()
		http.Error(w, "", http.StatusAccepted)
	}))

	m.Put("/speaker/beep", http.HandlerFunc(func (w http.ResponseWriter, r *http.Request) {
		// queue a beep
		http.Error(w, "", http.StatusAccepted)
	}))
*/

	address := ":8081"
	
	s := &http.Server{
		Addr:           address,
		Handler:        goweb.DefaultHttpHandler(),
		ReadTimeout:    10 * time.Second,
		WriteTimeout:   10 * time.Second,
		MaxHeaderBytes: 1 << 20,
	}
	
	log.Printf("Listening on port %s", address)
	listener, listenErr := net.Listen("tcp", address)

	log.Printf("%s", goweb.DefaultHttpHandler())
	
	if listenErr != nil {
		log.Fatalf("Could not listen: %s", listenErr)
	}

	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt)
	go func() {
		for _ = range c {

			// sig is a ^C, handle it

			// stop the HTTP server
			log.Print("Stopping the server...")
			listener.Close()

			/*
			   Tidy up and tear down
			*/
			log.Print("Tearing down...")

			// TODO: tidy code up here

			log.Fatal("Finished - bye bye.  ;-)")

		}
	}()
	log.Fatalf("Error in Serve: %s", s.Serve(listener))

}
