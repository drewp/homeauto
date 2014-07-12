package main

import "github.com/go-martini/martini"
import "github.com/tarm/goserial"
import "log"
import "io"
import "net/http"
import "image/color"
import "color/hex"
import "strconv"
import "time"
import "net/textproto"
import "bufio"
import "errors"

const ledCount = 3

type Board struct {
	ser       io.ReadWriteCloser
	LedColors [ledCount]color.Color
}

func OpenBoard(dev string) (*Board, error) {
	c := &serial.Config{Name: dev, Baud: 115200}
	ser, err := serial.OpenPort(c)
	if err != nil {
		return nil, err
	}
	log.Printf("wait for arduino to start up")
	time.Sleep(2 * time.Second)
	b := &Board{ser: ser}
	for i := 0; i < ledCount; i++ {
		b.LedColors[i] = color.RGBA{}
	}
	return b, err
}

func (b *Board) Write(cmd byte, msg []byte) error {
	head := make([]byte, 2)
	head[0] = 0x60
	head[1] = cmd
	_, err := b.ser.Write(head)
	if err != nil {
		return err
	}
	_, err = b.ser.Write(msg)
	if err != nil {
		return err
	}
	return err
}

func (b *Board) UpdateLeds() error {
	bytes := make([]byte, 9)

	for i := 0; i < ledCount; i++ {
		r, g, b, _ := b.LedColors[i].RGBA()
		bytes[i*3+0] = uint8(r)
		bytes[i*3+1] = uint8(g)
		bytes[i*3+2] = uint8(b)
	}
	return b.Write(0, bytes)
}

func (b *Board) ReadDht() (string, error) {
	for try := 0; try < 5; try++ {
		err := b.Write(0x2, make([]byte, 0))
		if err != nil {
			continue
		}

		reader := textproto.NewReader(bufio.NewReader(b.ser))
		json, err := reader.ReadLine()
		if err != nil {
			continue
		}
		return json, nil
	}
	return "", errors.New("failed after all retries")
}

func getBodyStringColor(req *http.Request) (c color.Color, err error) {
	bytes := make([]byte, 1024)
	n, err := req.Body.Read(bytes)
	body := hex.Hex(string(bytes[:n]))
	if err != nil {
		return
	}
	r, g, b := hex.HexToRGB(body)
	return color.RGBA{r, g, b, 0}, nil
}

func main() {
	board, err := OpenBoard("/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A9YLHR7R-if00-port0")
	if err != nil {
		log.Fatal(err)
	}

	m := martini.Classic()
	m.Martini.Use(martini.Static("static"))
	m.Get("/", martini.Static("static", martini.StaticOptions{}))
	m.Put("/led/:id", func(req *http.Request, params martini.Params) (int, string) {
		color, err := getBodyStringColor(req)
		if err != nil {
			return 400, ""
		}
		which, err := strconv.Atoi(params["id"])
		if err != nil {
			return 400, ""
		}
		
		board.LedColors[which] = color
		err = board.UpdateLeds()
		if err != nil {
			return 500, ""
		}
		
		return 200, "ok"
	})
	m.Get("/led", func() string {
		return "['#ff0000', '#ff0000']"
	})
	m.Put("/led", func(req *http.Request) (int, string) {
		color, err := getBodyStringColor(req)
		if err != nil {
			return 400, ""
		}

		for i := 0; i < ledCount; i++ {
			board.LedColors[i] = color
		}
		err = board.UpdateLeds()

		return 200, "ok"
	})
	m.Get("/dht", func() (int, string) {
		json, err := board.ReadDht()
		if err != nil {
			return 500, ""
		}
		return 200, json
	})
	log.Printf("serving")
	m.Run()
}
