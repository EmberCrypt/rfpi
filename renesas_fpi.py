from time import sleep, time
import logging
import sys
import numpy

from defs import *
from flashcomm import RenesasFlashComm



class RenesasFlashProgrammer():
    """Implements the Renesas flash programming interface"""

    COMMAND_RESET                = 0x00
    COMMAND_VERIFY               = 0x13
    COMMAND_19                   = 0x19
    COMMAND_CHIP_ERASE           = 0x20
    COMMAND_BLOCK_ERASE          = 0x22
    COMMAND_BLOCK_BLANK_CHECK    = 0x32
    COMMAND_PROGRAMMING          = 0x40
    COMMAND_READ                 = 0x50
    COMMAND_STATUS               = 0x70
    COMMAND_OSC_FREQUENCY_SET    = 0x90
    COMMAND_BAUD_RATE_SET        = 0x9a
    COMMAND_SECURITY_SET         = 0xa0
    COMMAND_SECURITY_GET         = 0xa1
    COMMAND_SECURITY_RELEASE     = 0xa2
    COMMAND_A4                   = 0xa4
    COMMAND_CHECKSUM             = 0xb0
    COMMAND_SIGNATURE            = 0xc0
    COMMAND_VERSION_GET          = 0xc5
    COMMAND_D0                   = 0xd0

    """Status response bytes"""
    STATUS_COMMAND_ERROR     = 0x04
    STATUS_PARAM_ERROR       = 0x05
    STATUS_ACK               = 0x06
    STATUS_CHECKSUM_ERROR    = 0x07
    STATUS_VERIFY_ERROR      = 0x0f
    STATUS_PROTECT_ERROR     = 0x10
    STATUS_NACK              = 0x15
    STATUS_MRG10_ERROR       = 0x1a
    STATUS_MRG11_ERROR       = 0x1b
    STATUS_WRITE_ERROR       = 0x1c
    STATUS_READ_ERROR        = 0x20
    STATUS_BUSY              = 0xff

    BLK_SIZE                =   0x40       # For data frames TODO should possible do this in flashcomm

    def __init__(self, mcu_type, flashcomm = None):
        if not flashcomm:
            raise ValueError("Please specify flashcomm device")
        self.flashcomm = flashcomm
        # 3 bytes per address default
        self.n_bytes = 3
        # should get the timeout in 10ms
        self.timeout = 0.01
        # How big are the flash blocks 
        self.fl_block_size = 0x1000

        self.mcu_type = mcu_type


    def reset(self):
        ''' Generic reset sequence - initialise the communication (depending on target and comm_mode) and then send the reset command '''
        r = self.flashcomm.reset_bl() # execute the right reset 
        if r:
            raise ValueError("Bootloader mode reset failed...")
        try:
            self.reset_command()
        except (NoResponseError, InvalidHeaderError, InvalidFooterError, InvalidChecksumError, NoAckError, InvalidFrameError) as e:
            logging.debug(e)
            return -1
        return 0

    


    def fp_mode(self):
        '''
            Resets the MCU into flash programming mode and sends the reset command
        '''
        ret = self.reset()
        if ret == -1:
            return -1
        try:
            self.reset_command()
        except (NoResponseError, InvalidHeaderError, InvalidFooterError, InvalidChecksumError, NoAckError, InvalidFrameError) as e:
            logging.debug(e)
            logging.debug("No response on reset command")
            return -1
        return 0

    def recv(self):
        '''Receives and returns a dataframe, throws an exception if anything other than an ACK is observed'''
        ret = []
        st = time()
        while (not ret) and (time() < st + self.timeout):
            try:
                if self.flashcomm.comm_mode == Comm_Mode.SPI and self.flashcomm.type == MCU_Type.R78K0:
                    self.flashcomm.send_command_frame(self.COMMAND_STATUS)  # only for SPI 78k0 - bastard 
                ret = self.flashcomm.recv_data_frame()
            except (InvalidFrameError, NoResponseError) as e:
                pass
        if not ret:
            raise InvalidFrameError('Didn\'t receive a frame after timeout')
        #if ret[0] == self.STATUS_PARAM_ERROR or ret[0] == self.STATUS_NACK:
        #    raise NoAckError("Received status {:02x}".format(ret[0]))
        return ret

    def calc_timings(self):
        """Since all devices require different timings, let's try to automatically detect these"""
        rst_off_orig = 0.1
        rst_time_orig = 0.0056
        rst_cmd_orig = 0.05
        post_flmd_orig = 0.05


        step_size = 3
        for flmd in range(11):
            for rst_off in numpy.arange(0, rst_off_orig, rst_off_orig/step_size):
                for post_flmd in numpy.arange(0, post_flmd_orig, rst_off_orig/step_size):
                    for rst_time in numpy.arange(0, rst_time_orig, rst_time_orig/step_size):
                        for rst_cmd in numpy.arange(0, rst_cmd_orig, rst_cmd_orig/step_size):
                            self.flashcomm.set_timings(rst_off, rst_time, rst_cmd, post_flmd)
                            if self.fp_mode() == 0:
                                logging.info("Found values: RST OFF {}, POST_FLMD {}, RST_TIME {}, RST_CMD {}".format(rst_off, post_flmd, rst_time, rst_cmd)) 
                                return

    def _get_addr_data(self, addr_start, addr_end, n_b = None):
        n_bytes = n_b if n_b is not None else self.n_bytes
        return [(addr_start >> (i*8)) & 0xff for i in range(n_bytes - 1, -1, -1)] + [(addr_end >> (i*8)) & 0xff for i in range(n_bytes - 1, -1, -1)] 



    def get_signature(self):
        self.flashcomm.send_command_frame(self.COMMAND_SIGNATURE)
        # Get status frame
        resp = self.recv()
        #self.flashcomm.send_data_frame([0x6]) # TODO sometimes necessary sometimes not
        # Get signature
        return self.recv()

    def reset_command(self):
        self.flashcomm.send_command_frame(self.COMMAND_RESET)
        return self.recv() 

    def security_release(self):
        self.flashcomm.send_command_frame(self.COMMAND_SECURITY_RELEASE)
        return self.recv()

    def security_get(self):
        self.flashcomm.send_command_frame(self.COMMAND_SECURITY_GET)
        return self.recv()

    def set_frequency(self, freq_data):
        """Sets frequency of the microcontroller (in khz)"""
        self.flashcomm.send_command_frame(self.COMMAND_OSC_FREQUENCY_SET, freq_data)
        return self.recv() 

    def test_cmd(self, cmd, args = []):
        self.flashcomm.send_command_frame(cmd, args)
        sleep(1)
        _r = self.recv()
        if _r != cmd.to_bytes(1, byteorder = "big"):
            #return _r 
            logging.info("Return {}: {}".format(cmd, _r))
        sleep(1)
        return self.recv()

    def read_memory(self, addr_start, n_bytes, out_file = None):
        """Reads memory from the V850"""
        data = self._get_addr_data(addr_start, addr_start + n_bytes - 1)    # n_bytes - 1 because of weird alignment on the MCU - request 0-0xff to read out first 0x100 bytes
        self.flashcomm.send_command_frame(self.COMMAND_READ, data)
        ret = self.flashcomm.recv_data_frame()
        if ret[0] == 0x6:
            if out_file:
                with open(out_file, 'wb') as out_f:
                    pass
            logging.info("DJONKO DJONKO MANEEEEE")
            self.timeout = 0.5
            self.flashcomm.send_data_frame([0x6])
            dat = self.recv()
            n_rcvd = len(dat)
            logging.info("DJONKO DJONKO ZWEI received {}".format(n_rcvd))
            while dat:
                if out_file:
                    with open(out_file, 'ab') as out_f:
                        out_f.write(dat)
                if n_rcvd >= n_bytes:
                    return 0
                sleep(0.1)
                self.flashcomm.send_data_frame([0x6])
                dat = self.recv()
                n_rcvd += len(dat)
                logging.info("n_rcvd: {}\t n_bytes:{}".format(n_rcvd, n_bytes))
        return ret

    def baud_rate_set(self, voltage = 0x32):
        self.flashcomm.send_command_frame(self.COMMAND_BAUD_RATE_SET, [0x00, voltage]) # for 5V 
        #self.flashcomm.send_command_frame(self.COMMAND_BAUD_RATE_SET, [0x00, 0x21]) # for 3.3V 
        return self.recv()


    def get_version(self):
        self.flashcomm.send_command_frame(self.COMMAND_VERSION_GET)
        resp = self.recv()
        return self.recv()

    def get_security(self):
        self.flashcomm.send_command_frame(self.COMMAND_VERSION_GET)
        resp = self.flashcomm.recv_data_frame()
        return self.recv()

    def get_checksum(self, addr_start, addr_end, callback_func = None):
        """Gets checksum of a certain address area"""
        data = self._get_addr_data(addr_start, addr_end)
        self.flashcomm.send_command_frame(self.COMMAND_CHECKSUM, data, callback_func)
        # Get the status frame
        _ret = self.recv()
        if self.chk_return(self.COMMAND_CHECKSUM, _ret):
            return _ret
        # Get the checksum
        chk = self.flashcomm.recv_data_frame()  # Checksum does not need status frame for some reason
        return chk

    def verify(self, addr_start, bin_data, n_bytes = 0):
        '''Verifies that the data is programmed in the range start_addr:end_addr'''
        self.timeout = 0.1
        if not n_bytes:
            n_bytes = len(bin_data)
        data = self._get_addr_data(addr_start, addr_start + n_bytes - 1)
        self.flashcomm.send_command_frame(self.COMMAND_VERIFY, data)
        # Check if ACK received, return if no bin_data provided
        _ret = self.recv()
        if self.chk_return(self.COMMAND_VERIFY, _ret) or not bin_data:
            return _ret
        self.flashcomm.send_data_frame(bin_data)
        sleep(0.1)
        return self.recv()

    def program(self, addr_start, bin_data, n_bytes = 0):
        '''Programs the binary data to the specified address (in chunks of 0x100 bytes)'''
        self.timeout = 0.1
        # Set the timeout since programming takes longer
        if not n_bytes:
            n_bytes = len(bin_data)
        data = self._get_addr_data(addr_start, addr_start + n_bytes - 1)
        self.flashcomm.send_command_frame(self.COMMAND_PROGRAMMING, data)
        sleep(0.01)
        # Check if ACK received, return if no data provided
        _ret = self.recv()
        if self.chk_return(self.COMMAND_PROGRAMMING, _ret):
            return _ret
        self.flashcomm.send_data_frame(bin_data)
        sleep(0.4)
        ret = self.recv()
        logging.info(f"{ret}")
        return ret


    def recv_uart(self, baud = 115200, out_file = None):
        '''Reads the bytes from the UART after the dump routine has been uploaded'''
        self.flashcomm.serial_port.baudrate = baud
        if out_file:
            with open(out_file, 'wb') as out_f:
                pass
        self.flashcomm.normal_mode()
        sleep(0.1)
        RECV_SIZE = 0x1000
        dat = self.flashcomm.recv(RECV_SIZE)
        while dat:
            if out_file:
                with open(out_file, 'ab') as out_f:
                    out_f.write(dat)
            dat = self.flashcomm.recv(RECV_SIZE)
        self.flashcomm.mcu_off()

    def overwrite_bootl(self, firmware):
        '''Overwrites the boot section with the firmware contained in firm_file'''
        self.timeout = 0.5  # set timeout large enough
        if self.fp_mode() != 0:
            logging.error("Flash programming mode could not be activated")
            return
        with open(firmware, 'rb') as dump_routine:
            bytes_read = list(dump_routine.read())
        # Fill in missing FF's to align to page size
        l = len(bytes_read)
        for i in range(l, (l | 0xff) + 1):
            bytes_read.append(0xff)
        for i in range(0, len(bytes_read), self.fl_block_size):
            self.block_erase(i)
        sleep(0.1)
        for i in range(0, len(bytes_read), 0x100):
            self.program(i, bytes_read[i:i+0x100])
            sleep(0.1)

    def block_erase(self, addr_start):
        '''Erases block of 0x100 bytes starting from addr_start'''
        t_o = self.timeout
        self.timeout = 0.3

        # Align address to a 1kB boundary
        data = self._get_addr_data(addr_start, addr_start + self.fl_block_size - 1)
        if self.flashcomm.type == MCU_Type.RL78:
            data = data[::]
        self.flashcomm.send_command_frame(self.COMMAND_BLOCK_ERASE, data)
        _r = self.recv()

        self.timeout = t_o

        if _r[0] != 0x06:  
            return _r


        sleep(0.2)
        _r = self.recv()
        return _r


    def chip_erase(self):
        self.flashcomm.send_command_frame(self.COMMAND_CHIP_ERASE)
        return self.recv()

    def security_set(self, sec_flag, boot_blk_no, fswstl = None, fswsth = None, fswel = None, fsweh = None): 
        ''' Sets the security settings of the MCU
            :param sec_flag: 1 | 1 | 1 | Boot area write prot | 1 | write prot | blk erase prot | chip erase prot
            :param boot_blk_no: boot block cluster last block number
        '''
        self.flashcomm.send_command_frame(self.COMMAND_SECURITY_SET, [0x00, 0x00])
        # for the 78k0r, add flash shield window start and end
        sec_data = [sec_flag & 0xff, boot_blk_no & 0x7f]
        if fswstl != None and fswel != None:
            sec_data += [fswstl, fswsth, fswel, fsweh]
        ret = self.recv()
        sleep(0.003)
        self.flashcomm.send_data_frame(sec_data)
        ret = self.recv()
        if ret[0] == self.STATUS_PROTECT_ERROR:
            return ret
        ret = self.recv()
        return ret

    def cmd_a4(self):
        '''Tries out command a4'''
        self.flashcomm.send_command_frame(self.COMMAND_A4, [0x01, 0x00])
        ret = self.recv()
        ret = b""
        dat = self.flashcomm.recv(1)
        while dat:
            ret += dat
            dat = self.flashcomm.recv(1)
        logging.info([hex(b) for b in ret])
        logging.info("Length: %d" % len(ret))


    def get_checksums(self, start_addr, end_addr):
        '''Gets all (legitimate) checksums from start_addr to end_addr'''
        chks = []
        for i in range(start_addr, end_addr, 0x100):
            chk = self.get_checksum(i, i + 0xff)
            chksum = (chk[0] << 8) | chk[1]
            chks.append(chksum)
            print('[{:04x}]: {:04x}'.format(i, chksum))
            sleep(0.01)
        return chks

    def verify_bin(self, binary, addr_start=0):
        with open(binary, 'rb') as dump_routine:
            bytes_read = list(dump_routine.read())
        # Fill in missing FF's to align to page size
        l = len(bytes_read)
        for i in range(l, (l | 0xff) + 1):
            bytes_read.append(0xff)
        for i in range(0, len(bytes_read), 0x400):
            logging.info("Verifying block {:x}".format(i))
            if self.verify(i + addr_start , i + addr_start + 0x3ff, bytes_read[i:i+0x400])[1] != 0x6:
                logging.error("Verify error!")
            sleep(0.2)

    def get_blk_size(self, addr):
        ''' Default block size '''
        return 0x2000

    def flash(self, addr, binary):
        ''' Flashes the binary to the MCU '''
        with open(binary, 'rb') as _b:
            _firmware = list(_b.read())
        _len = len(_firmware)
        blk_size = self.get_blk_size(addr)

        if _len & 0xff != 0:
            for _i in range(_len, (_len | 0xff) + 1):
                _firmware.append(0xff)

        count = 0
        for _i in range(addr, addr + len(_firmware), blk_size):
            # We erase the block first - the erase block size is often different to the program block size, but we can just ignore the errors here
            self.block_erase(_i) 
            self.program(_i, _firmware[count:count + blk_size])
            count += blk_size

