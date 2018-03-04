import tempfile, subprocess, logging, os
log = logging.getLogger('arduino_code')

def writeMakefile(dev, tag, allLibs):
    return '''
BOARD_TAG = %(tag)s
USER_LIB_PATH := %(libs)s
ARDUINO_LIBS = %(arduinoLibs)s
MONITOR_PORT = %(dev)s

include /usr/share/arduino/Arduino.mk
            ''' % {
                'dev': dev,
                'tag': tag,
                'libs': os.path.abspath('arduino-libraries'),
                'arduinoLibs': ' '.join(allLibs),
               }

def writeCode(baudrate, devs, devCommandNum):
    generated = {
        'baudrate': baudrate,
        'includes': '',
        'global': '',
        'setups': '',
        'polls': '',
        'idles': '',
        'actions': '',            
    }
    for attr in ['includes', 'global', 'setups', 'polls', 'idles',
                 'actions']:
        for dev in devs:
            if attr == 'includes':
                gen = '\n'.join('#include "%s"\n' % inc
                                for inc in dev.generateIncludes())
            elif attr == 'global': gen = dev.generateGlobalCode()
            elif attr == 'setups': gen = dev.generateSetupCode()
            elif attr == 'polls': gen = dev.generatePollCode()
            elif attr == 'idles': gen = dev.generateIdleCode()
            elif attr == 'actions':
                code = dev.generateActionCode()
                if code:
                    gen = '''else if (cmd == %(cmdNum)s) {
                               {
                                 %(code)s
                               }
                               Serial.write('k');
                             }
                          ''' % dict(cmdNum=devCommandNum[dev.uri],
                                     code=code)
                else:
                    gen = ''
            else:
                raise NotImplementedError

            if gen:
                generated[attr] += '// for %s\n%s\n' % (dev.uri, gen.strip())

    code = '''
%(includes)s

%(global)s
byte frame=1;
unsigned long lastFrame=0; 

void setup() {
    Serial.begin(%(baudrate)d);
    Serial.flush();
    %(setups)s
}
        
void idle() {
    // this slowdown is to spend somewhat less time PWMing, to reduce
    // leaking from on channels to off ones (my shift register has no
    // latching)
    if (micros() < lastFrame + 80) {
      return;
    }
    lastFrame = micros();
    frame++;
    %(idles)s
}

void loop() {
    byte head, cmd;
    idle();
    if (Serial.available() >= 2) {
        head = Serial.read();
        if (head != 0x60) {
            Serial.flush();
            return;
        }
        cmd = Serial.read();
        if (cmd == 0x00) { // poll
          %(polls)s
          Serial.write('x');
        } else if (cmd == 0x01) { // get code checksum
          Serial.write("CODE_CHECKSUM");
        }
        %(actions)s
    }
}
        ''' % generated
    return code

def indent(code):
    try:
        with tempfile.SpooledTemporaryFile() as codeFile:
            codeFile.write(code)
            codeFile.seek(0)
            code = subprocess.check_output([
                'indent',
                '-linux',
                '-fc1', # ok to indent comments
                '-i4', # 4-space indent
                '-sob' # swallow blanks (not working)
            ], stdin=codeFile)
    except OSError as e:
        log.warn("indent failed (%r)", e)
    return code
    
