# Renesas flash programming interface implementation
from gpiozero import DigitalOutputDevice, SPIDevice
from time import sleep, time
import serial
import logging
import os.path


from defs import *

class RenesasFlashComm():
    """Handles the serial communication with the Renesas Flash interface"""
    

    """
        Minimum times necessary for the Flash Programming interface to be ready
        Dependent on Renesas chip 
    """
    RESET_OFF_TIME              =   0.01
    RESET_TIME                  =   0.0056
    RESET_CMD_TIME              =   0.02
    POST_FLMD                   =   0.01



    '''Amount of pulses required on FLMD0 for the serial protocol '''
    flmd_pulses = {
        MCU_Type.V850E: 
            {Comm_Mode.UART2: 0, Comm_Mode.SPI: 8},
        MCU_Type.D76F: {Comm_Mode.SPI: 0},
        MCU_Type.RH850: {Comm_Mode.SPI: 0, Comm_Mode.UART2: 0},
        MCU_Type.V850E2: {Comm_Mode.UART1:0, Comm_Mode.SPI: 8},
        MCU_Type.V850ES: {Comm_Mode.UART2: 0, Comm_Mode.SPI: 9},
        MCU_Type.R78K0: {Comm_Mode.UART2: 0, Comm_Mode.SPI: 8},
        MCU_Type.R78K0_Kx2: {Comm_Mode.TOOLD: 0},
        MCU_Type.R78K0R: {Comm_Mode.UART2: 0},
        MCU_Type.R32C: {Comm_Mode.UART2: 0}
        } # TODO move these to base classes



    def __init__(self, mcu_type, comm_mode, port = "/dev/serial0", baud_rate = 9600, gpio_flmd = 2, gpio_reset = 3):
        print("Starting the flash programming interface")
        print("----------------------------------------")
        print("FLMD0: GPIO{}\t MISO: 21\t MOSI: 19".format(gpio_flmd))
        print("RESET: GPIO{}\t CLK: 23".format(gpio_reset))
        print("----------------------------------------")
        # FLMD0 is GPIO2, RESET is GPIO22
        if comm_mode == Comm_Mode.TOOLD:
            self.flmd0 = DigitalOutputDevice(gpio_flmd, initial_value=0)
        else:
            self.flmd0 = DigitalOutputDevice(gpio_flmd, initial_value=1)

        self.reset = DigitalOutputDevice(gpio_reset, initial_value=0)
        self.comm_mode = comm_mode
        self.type = mcu_type
        self.port = port

        if comm_mode == Comm_Mode.SPI:
            # SPIdev to communicate over the flash programming interface
            self.spicomm = SPIDevice(port=0, device=0)
            # Configure SPI device
            self.spicomm._spi._interface.max_speed_hz = baud_rate
            self.spicomm._spi._set_clock_mode(3)
            self.serial_port = None
        elif comm_mode == Comm_Mode.UART2 or comm_mode == Comm_Mode.UART1:
            self.serial_port = serial.Serial(port, baud_rate, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE, timeout=0.1) # TODO poss change timeout depending on baud rate
        elif comm_mode == Comm_Mode.TOOLD:
            pass
        """Frame bytes"""
        self.FRAME_SOH = 0x01 
        self.FRAME_ETB = 0x17 
        self.FRAME_ETX = 0x03
        # For all devices except for RH850 and V850E2, observed STX was 0x2
        self.FRAME_STX = 0x02 
        # FRAME_STX differs depending on the type
        if self.type == MCU_Type.V850E2:
            self.FRAME_STX = 0x11 
        elif self.type == MCU_Type.RH850:
            self.FRAME_STX = 0x81


        ''' Reset functions for the specific mcu type. All other MCUs use the generic reset '''
        self.reset_funcs = {MCU_Type.RH850: self.rh850_reset, MCU_Type.R78K0R: self.fp_uart1, MCU_Type.R78K0_Kx2: self.toold_entry, MCU_Type.RL78: self.tool0_entry}
        ''' The amount of pulses for flmd0 '''
        if self.type in self.flmd_pulses:
            self.pulses = self.flmd_pulses[self.type][self.comm_mode]

        
    def set_timings(self, rst_off, rst_time, rst_cmd, post_flmd):
        '''Sets the timing parameters for the flash programming interface'''
        self.RESET_OFF_TIME = rst_off
        self.RESET_TIME = rst_time
        self.RESET_CMD_TIME = rst_cmd
        self.POST_FLMD = post_flmd

    
    def mcu_on(self):
        '''Operate in normal mode'''
        self.flmd0.off()
        self.reset.off()
        sleep(self.RESET_OFF_TIME)
        if self.serial_port:
            self.serial_port.reset_input_buffer()
        self.reset.on()

    def mcu_off(self):
        '''Turns off reset'''
        self.reset.off()
        self.flmd0.off()

    def reset_bl(self):
        ''' Calls the correct reset sequence for the mcu type '''
        _reset_f = self.reset_funcs.get(self.type, self.fp_generic)
        self.initial_reset()
        return _reset_f()

    def initial_reset(self):
        ''' The generic initial sequence (flmd on, reset off, ...) '''
        # pull reset low to restart
        self.reset.off()
        if self.comm_mode == Comm_Mode.TOOLD or self.comm_mode == Comm_Mode.TOOL0:
            self.tool = DigitalOutputDevice(18, initial_value = 0) # take the same pin as the UART RX
            self.flmd0.off()    # flmd0 acts as toolc
            self.tool.off()


        else:
            self.flmd0.on()

            if self.serial_port:
                self.serial_port.reset_input_buffer()

            sleep(self.RESET_OFF_TIME)

        # pull reset high
        self.reset.on()



    def rh850_reset(self):
        ''' TODO put this in something decent '''
        sleep(0.0056)
        for i in range(self.pulses):
            self.flmd0.off()
            self.flmd0.on()

        sleep(0.2)
        for i in range(30):
            self.send([0x00])
            sleep(0.0001)

        _b_recv = self.recv(1)
        if _b_recv != b'\x00':
            logging.error(_b_recv)
            raise NoResponseError("Did not receive 0 sync byte")
            
        # for bitrate
        self.send([0x55])
        _b_recv = self.recv(1)
        if _b_recv != b'\xc1':
            logging.error(_b_recv)
            raise NoResponseError("Set bitrate failed")

        return 0

    def tool0_entry(self):
        sleep(0.01)
        self.tool.on()
        self.tool.close()
        # Clean up pins & start 1 wire uart
        self.serial_port = serial.Serial(self.port, 115200, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE, timeout=0.1)

        # For 1 wire serial flash programming
        if 1:
            self.send([0x3a])
        else:
            # For OCD access
            self.send([0xc5])

    def toold_entry(self):
        self.flmd0.on()
        self.tool.on()

        for _cnt in range(3):
            sleep(0.01)
            for _i in range(2):
                self.flmd0.off()
                sleep(0.001)
                self.flmd0.on()
                sleep(0.001)

            sleep(0.005)

            for _i in range(7):
                self.tool.off()
                sleep(0.001)
                self.tool.on()
                sleep(0.001)


        self.tool.close()
        # Clean up pins & start 1 wire uart
        self.serial_port = serial.Serial("/dev/ttyAMA0", 125000, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE, timeout=0.1)
        self.serial_port.reset_input_buffer()
        self.reset.on()

        _sync_b = self.recv(1)
        if _sync_b != b'\x00':
            raise NoResponseError("Did not receive 0 sync byte")

        return 0

    def fp_uart1(self):
        ''' Handles the reset over 1-wire UART (on TOOL0 pin) on 78k0r'''
        sleep(self.RESET_TIME)

        # wait for the 0 byte to sync
        f_byte = b""
        st_t = time()
        while f_byte != b"\x00":
            f_byte = self.recv(1)
            if time() < st_t + 0.01:
                return -1
        self.send([0])
        # Send two zero bytes for the reset command
        sleep(0.01)
        self.send([0])
        self.send([0])

        # read back the three bytes we just sent
        self.serial_port.read(3)

    def fp_generic(self):
        ''' Handles the generic FP sequence for UART2 and SPI on 78k0, v850 '''
        # recommended value is 0.0056
        sleep(self.RESET_TIME)

        # pulse FLMD0 an amount of times to set SPI mode
        logging.debug("pulsing FLMD {} times".format(self.pulses))

        for i in range(self.pulses):
            self.flmd0.off()
            self.flmd0.on()

        self.flmd0.on()

        # wait for RESET command processing ! IMPORTANT do not remove - and if does not work, then fiddle with timing !
        sleep(self.RESET_CMD_TIME)

        # For UART mode, to synch clocks
        if self.comm_mode == Comm_Mode.UART2:
            self.send([0x00])
            sleep(0.01)
            self.send([0x00])


        if self.serial_port:
            self.serial_port.reset_input_buffer()

        sleep(self.POST_FLMD)


    def checksum(self, data):
        ''' Calculates checksum for the frame '''
        s = 0
        for b in data:
            s = (s - b) & 0xff
        return s & 0xff

    def send(self, data, callback_func = None, d_frame = 0):
        """Sends the buffer with data over the serial interface. """
        # Split data into two parts: up untill the trigger byte and then the rest
        if self.comm_mode == Comm_Mode.SPI:
            if callback_func:
                self.spicomm._spi.transfer(data[:-1])
                callback_func()
                self.spicomm._spi.transfer([data[-1]])
            else:
                if d_frame:
                    for b in data:
                        self.spicomm._spi.transfer([b])
                else:
                    self.spicomm._spi.transfer(data)

        elif self.comm_mode == Comm_Mode.UART2:
            self.serial_port.write(bytearray(data)) 
        else:
            self.serial_port.write(bytearray(data)) 
            b_recv = 0
            # read back the bytes we sent since it's a single wire
            while b_recv < len(data):
                b = self.serial_port.read(1)
                if b:
                    b_recv += 1



    def recv(self, n_bytes):
        """Receives data over the serial interface"""
        if self.comm_mode == Comm_Mode.SPI:
            return self.spicomm._spi.transfer([0x00 for i in range(n_bytes)])
        else:
            return self.serial_port.read(n_bytes)


    def print_data(self, data):
        logging.warning(' '.join('{:02x}'.format(x) for x in data))


    def recv_data_frame(self):
        # get header first - 2 bytes for V850ES
        data = self.recv(1)
        if not data or data[0] == 0x00:
            raise NoResponseError("No frame received")

        n_recvd = 0
        while (data[0] != self.FRAME_STX and n_recvd < 0x100):
            data = self.recv(1)
            logging.debug(data)
            n_recvd += 1
            #if n_recvd >= 0x100 or data != 0xff:
            if n_recvd >= 0x100 or data == b'':
                raise InvalidHeaderError("Received frame is not a data frame: " + " ".join(['{:02x}'.format(b) for b in data]))

        if self.type == MCU_Type.V850E2 or self.type == MCU_Type.RH850:
            data += self.recv(2)
            if len(data) < 3:
                raise InvalidHeaderError("Frame length wrong: " + " ".join(['{:02x}'.format(b) for b in data]))
            d_len = (data[1] << 0x8) + data[2]
        else:
            data += self.recv(1)
            if len(data) > 1:
                d_len = data[1]
                if d_len == 0:
                    d_len = 256
            else:
                raise InvalidHeaderError("Something data_len" + " ".join(['{:02x}'.format(b) for b in data]))


        # To prevent timeouts - receive per byte
        len_total = len(data) + d_len + 2

        st_t = time()
        while len(data) < len_total and time() < st_t + 1:
            _b = self.recv(0x1)
            data += _b
        
        #data = data + self.recv(d_len + 2)
        if data[-1] != self.FRAME_ETB and data[-1] != self.FRAME_ETX:
            raise InvalidFooterError("Format error in footer: "+ " ".join(['{:02x}'.format(b) for b in data]))
        chk = self.checksum(data[1:-2])
        if data[-2] != chk:
            raise InvalidChecksumError("Incorrect checksum: "+ " ".join(['{:02x}'.format(b) for b in data]))
        logging.debug(' '.join('{:02x}'.format(x) for x in data))
        # TODO change this to n_len_bytes or so
        if self.type == MCU_Type.V850E2 or self.type == MCU_Type.RH850:
            return data[3:-2]
        else:
            return data[2:-2]

    def make_frame(self, header, data, wrong_chk_sum = 0):
        if self.type == MCU_Type.V850E2 or self.type == MCU_Type.RH850:
            l = len(data)
            d = [header, (l >> 8) & 0xff, l & 0xff]
        else:
            d = [header, len(data) & 0xff]
        d = d + data
        if wrong_chk_sum:
            d.append((self.checksum(d[1:]) + 1) & 0xff)
        else:
            d.append(self.checksum(d[1:]))
        d.append(self.FRAME_ETX)
        return d


    def send_command_frame(self, cmd, data = [], callback_func = None, wrong_chk_sum = 0):
        """Sends a command to the chip
        """
        data_bytes = [cmd] + data
        d = self.make_frame(self.FRAME_SOH, data_bytes, wrong_chk_sum)
        logging.debug(' '.join('{:02x}'.format(x) for x in d))
        self.send(d, callback_func)

    def send_data_frame(self, data=[]):
        d = self.make_frame(self.FRAME_STX, data)
        logging.debug(' '.join('{:02x}'.format(x) for x in d))
        self.send(d, d_frame = 1)




