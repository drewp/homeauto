package main

import (
	"io/ioutil"
	"log"
	"net/http"
	"strconv"
	"encoding/json"
	"github.com/bmizerany/pat"
	"github.com/mrmorphic/hwio"
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
	
	if err := hwio.PinMode(pins.InMotion,		hwio.INPUT_PULLUP); err != nil { panic(err) }
	if err := hwio.PinMode(pins.InSwitch1,		hwio.INPUT_PULLUP); err != nil { panic(err) }
	if err := hwio.PinMode(pins.InSwitch2,		hwio.INPUT_PULLUP); err != nil { panic(err) }
	if err := hwio.PinMode(pins.InSwitch3,		hwio.INPUT_PULLUP); err != nil { panic(err) }
	if err := hwio.PinMode(pins.InDoorClosed,	hwio.INPUT_PULLUP); err != nil { panic(err) }
	if err := hwio.PinMode(pins.OutLed,			hwio.OUTPUT); err != nil { panic(err) }
	if err := hwio.PinMode(pins.OutSpeaker,		hwio.OUTPUT); err != nil { panic(err) }
	if err := hwio.PinMode(pins.OutStrike,		hwio.OUTPUT); err != nil { panic(err) }
	return pins
}
	
func main() {
	pins := SetupIo()

	m := pat.New()
	
	m.Get("/", http.HandlerFunc(func (w http.ResponseWriter, r *http.Request) {
		http.ServeFile(w, r, "index.html")
	}));

	m.Get("/static/:any", http.FileServer(http.Dir("./")));

	m.Get("/status", http.HandlerFunc(func (w http.ResponseWriter, r *http.Request) {
		jsonEncode := json.NewEncoder(w)
		jsonEncode.Encode(map[string]int{
			"motion": DigitalRead(pins.InMotion),
			"switch1": DigitalRead(pins.InSwitch1),
			"switch2": DigitalRead(pins.InSwitch2),
			"switch3": DigitalRead(pins.InSwitch3),
			"doorClosed": DigitalRead(pins.InDoorClosed),
			"led": pins.LastOutLed,
		})
	}));

	m.Put("/led", http.HandlerFunc(func (w http.ResponseWriter, r *http.Request) {
		body, err := ioutil.ReadAll(r.Body)
		if err != nil {
			panic(err)
		}
		level, err := strconv.Atoi(string(body[:]))
		if err != nil {
			http.Error(w, "body must be '0' or '1'", http.StatusBadRequest)
			return
		}

		hwio.DigitalWrite(pins.OutLed, level)
		pins.LastOutLed = level

		http.Error(w, "", http.StatusAccepted)
	}));

	http.Handle("/", m)
	log.Printf("Listening on port 8080")
	err := http.ListenAndServe(":8080", nil)
	if err != nil {
		log.Fatal("ListenAndServe: ", err)
	}
}
