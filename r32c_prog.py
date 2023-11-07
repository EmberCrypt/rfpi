from flashcomm import RenesasFlashComm
from renesas_fpi import RenesasFlashProgrammer
from defs import Comm_Mode, MCU_Type
import logging

from time import sleep

class R32CProgrammer(RenesasFlashProgrammer):
    ''' 
        For interfacing with the R32C bootloader
        Half experimented, half from https://people.redhat.com/dj/m32c/flash-guide.pdf
        Each page is 0x100 byte long

    '''

    GET_STATUS  =   0x70
    CLR_STATUS  =   0x50
    SEND_MSB    =   0x48
    CHIP_UNLOCK =   0xf5
    PAGE_READ   =   0xff

    # TODO fill in for other R8C, ... Seems funky addresses to me
    LOCK_REG = {MCU_Type.R32C: 0xFFFFFFE8}


    def __init__(self, **kwargs):
        #super().__init__(MCU_Type.Rxx, Comm_Mode.UART2, baud_rate = 9600)
        super().__init__(MCU_Type.R32C, **kwargs)



    def reset(self):
        ''' Takes care of the reset for the R32C. FLMD0 pin serves as CNVss/MODE '''
        self.flashcomm.reset.off()
        self.flashcomm.flmd0.on()
        sleep(0.001)
        self.flashcomm.reset.on()

        sleep(0.02)

        for i in range(16):
            self.flashcomm.send([0x00])
            sleep(0.01)

        sleep(0.01)

        self.flashcomm.send([0xb0])
        _r = self.flashcomm.recv(1)
        if _r != b'\xb0':
            logging.debug(_r)
            raise ValueError("Baud rate setting failed")
        return 0


    def status(self):
        ''' 
            sends the old status frame and returns it 
            Bit 7 of SRD1 is set when the bootloader is ready for another command. 
            Bit 5 is set when an erase command fails. 
            Bit 4 is set when a program command fails. 
            Bits 3 and 2 of SRD2 tell you if you've "unlocked" the flash by providing the correct unlock key

            SRD1 SRD2
            | BL ready | | ERASE fail | PROG fail | | | | |         | | | | | X | X | | |
            00: no_key provided
            01: wrong key provided
            11: correct key provided

            '''
        self.flashcomm.send([self.GET_STATUS])
        return self.flashcomm.recv(2)

    def clr_status(self):
        '''
            Clears the bootloader status
        '''
        self.flashcomm.send([self.CLR_STATUS])

    def chip_unlock(self, code = [0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff]):
        '''
            Unlocks the chip
        '''
        a = self.LOCK_REG[self.mcu_type]
        self.flashcomm.send([self.CHIP_UNLOCK, a & 0xff, (a >> 0x8) & 0xff, (a >> 0x10) & 0xff, 0x7] + code)

        sleep(0.02)
        _st = self.status()

        return _st

         

    def read_page(self, addr):
        '''
            Issue a single read command to get a page (0x100 byte)
        '''
        self.flashcomm.send([self.PAGE_READ, (addr >> 0x8) & 0xff, (addr >> 0x10) & 0xff])
        sleep(0.5)
        _r = self.flashcomm.recv(0x100)
        return _r

    def read(self, addr_start, n_bytes, out_file = None):
        self.chip_unlock()
        _firm = b''
        for _i in range(addr_start, addr_start + n_bytes, 0x100):
            _chunk = self.read_page(_i)
            _firm += _chunk
            if len(_chunk) != 0x100:
                logging.error(f"Chunk {_i:04x} read not 0x100 aligned")
                return _firm
        return _firm


    def erase_chip(self):
        self.flashcomm.send([0xa7, 0xd0])




    

if __name__ == "__main__":
    prog = R32CProgrammer()
    prog.reset()
    prog.chip_unlock()
    
