import logging
from time import sleep
import sys

from renesas_fpi import RenesasFlashProgrammer
from defs import *


class RH850Programmer(RenesasFlashProgrammer):
    ''' Program the RH850 '''

    ''' RH850 uses different command bytes for some reason '''
    COMMAND_CHECKSUM        =   0x18
    COMMAND_READ            =   0x15
    COMMAND_BLOCK_ERASE     =   0x12
    COMMAND_PROGRAMMING     =   0x13
    COMMAND_ID_CODE         =   0x30
    COMMAND_RFO             =   0x27
    COMMAND_WFO             =   0x26


    ''' Unsure about these commands '''
    CHIP_INFO               =   0x3a


    def __init__(self, **kwargs):
        super().__init__(MCU_Type.RH850, **kwargs)
        logging.info("RH850 instance initiated...")
        # Device specifics 
        self.timeout = 0.1
        self.n_bytes = 4
        self.fl_block_size = 0x2000

        # TODO adjust this based on chip
        self.freq = 0xf42400
        self.int_freq = 0x05b8d800

    def rfo(self):
        ''' Read flash options '''
        self.flashcomm.send_command_frame(self.COMMAND_RFO)
        _r = self.recv()
        if _r != b'\x27':
            raise ValueError("sheit")
        self.flashcomm.send_data_frame([self.COMMAND_RFO])
        _r = self.recv()
        return _r

    def wfo(self, option_bytes = [0xcf, 0xff, 0x27, 0xba, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff]):
        ''' Write Flash options '''
        self.flashcomm.send_command_frame(self.COMMAND_WFO, option_bytes)
        sleep(0.5)
        _r = self.recv()
        if _r[0] != self.COMMAND_WFO:
            raise ValueError("Error")
        return _r
        
    
    def freq_set(self):
        '''Not quite figured out what the arguments to this are. These hardcoded values set the baud rate to 9600 with an oscillator of 16MHz '''
        #self.flashcomm.send_command_frame(0x32, [0, 0x7a, 0x12, 0x00, 0x04, 0xc4, 0xb4, 0x00]) # for 57600
        #self.flashcomm.send_command_frame(0x32, [0, 0xf4, 0x24, 0x00, 0x04, 0xc4, 0xb4, 0x00]) # for 9600 (f42400 = 16000000)
        #self.flashcomm.send_command_frame(0x32, [0, self.freq >> 8, self.freq & 0xff, 0x00, 0x04, 0xc4, 0xb4, 0x00]) # for 9600
        #self.flashcomm.send_command_frame(0x32, [0, 0x1, 0xc2, 0x00, 0x04, 0xc4, 0xb4, 0x00]) # for 115200?
        self.flashcomm.send_command_frame(0x32, [(self.freq >> 0x18) & 0xff, (self.freq >> 0x10) & 0xff, (self.freq >> 0x8) & 0xff, self.freq & 0xff, (self.int_freq >> 0x18) & 0xff, (self.int_freq >> 0x10) & 0xff, (self.int_freq >> 0x8) & 0xff, self.int_freq & 0xff])
        _r = self.recv()
        if _r != b'\x32':
            raise ValueError("Command 32 failed")
        sleep(0.1)
        self.flashcomm.send_data_frame([0x32])
        _r = self.recv()
        return _r



    def cmd_38(self):
        self.flashcomm.send_command_frame(0x38)
        _r = self.recv()
        if _r != b'\x38':
            return _r
        self.flashcomm.send_data_frame([0x38])
        _r = self.recv()
        return _r

    def cmd_34(self):
        ''' Not sure what it does '''
        self.flashcomm.send_command_frame(0x34, [0, 0, 0x25, 0x80]) # Sets baud rate you shlonkendonkel
        _r = self.recv()
        if _r != b'\x34':
            raise ValueError("Cmd 34 failed")

    def cmd_2c(self):
        self.flashcomm.send_command_frame(0x2c)
        _r = self.recv()
        if _r != b'\x2c':
            raise ValueError("Cmd 2c failed")
        self.flashcomm.send_data_frame([0x2c])
        return self.recv()

    def pre_reset(self):
        if self.flashcomm.reset_bl() != 0:
            raise NoResponseError("RH850 baud sync failed")
        self.cmd_38()
        self.freq_set()
        self.cmd_34()

    def reset(self):
        ''' RH850 seems to require a very specific reset sequence. After this - requires post_reset and 3a'''
        _r = self.pre_reset()
        if _r == -1:
            return -1
        # Check return of reset command - bootloader can be locked
        _r = self.reset_command()
        return _r

    def post_reset(self):
        _r = self.cmd_2c()
        return _r


    def wrong_msg_size(self, cmd = 0x11, n_bytes = 0x100):
        self.flashcomm.send_command_frame(cmd, data = [0, 0, 0, 0, 0, 0, 3, 0xff] + [0xff for i in range(n_bytes - 8)], wrong_chk_sum = 0)
        sleep(0.3)
        return self.recv()
        

    def read(self, addr_start, n_bytes):
        data = self._get_addr_data(addr_start, addr_start + n_bytes - 1)
        self.flashcomm.send_command_frame(self.COMMAND_READ, data)
        _r = self.flashcomm.recv_data_frame()
        if not _r or _r[0] != self.COMMAND_READ:
            return _r
        self.flashcomm.send_data_frame([self.COMMAND_READ])
        n_rcvd = 0
        bytes_ = b''
        while n_rcvd < n_bytes:
            _r = self.flashcomm.recv_data_frame()
            logging.info(_r)
            bytes_ += _r[1:]
            n_rcvd += len(_r) - 1
            if n_rcvd < n_bytes:
                self.flashcomm.send_data_frame([self.COMMAND_READ])
        logging.info(bytes_)
        return bytes_

        
    def block_erase(self, addr):
        ''' Erase the block on given address '''
        data = self._get_addr_data(addr, addr)[0:4] 
        self.flashcomm.send_command_frame(self.COMMAND_BLOCK_ERASE, data)
        sleep(0.5)
        _r = self.recv()
        return _r

    def cmd_30(self, ocd_id = [0xff for _i in range(0x20)]):
        ''' Possibly unlocks the old bootloader with the OCD ID? '''
        self.flashcomm.send_command_frame(0x30, ocd_id)
        _r = self.recv()
        return _r
    
    def cmd_3a(self):
        self.flashcomm.send_command_frame(0x3a)
        _r = self.recv()
        self.flashcomm.send_data_frame([0x3a])
        return self.recv()

    def cmd_3b(self):
        for _i in range(0xc):
            self.flashcomm.send_command_frame(0x3b, [_i])
            _r = self.recv()

    def program(self, addr_start, bin_data):
        # For rh850: there's a 0x13 in front of every data frame
        return super().program(addr_start, [self.COMMAND_PROGRAMMING] + bin_data, n_bytes = len(bin_data))

    def get_blk_size(self, addr):
        if addr >= 0xff200000:
            blk_size = 0x40
        else:
            blk_size = 0x400
        return blk_size

    def verify(self, addr_start, bin_data):
        return super().verify(addr_start, [self.COMMAND_VERIFY] + bin_data, n_bytes = len(bin_data))


    def checksum(self, addr_st, addr_e):
        return super().get_checksum(addr_st, addr_e)

    def chk_return(self, cmd, ret_data):
        ''' Checks the return value of a command '''
        if not ret_data:
            return -1
        if ret_data[0] == cmd:
            return 0
        return -1

