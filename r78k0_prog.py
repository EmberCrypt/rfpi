import sys
from time import sleep

from renesas_fpi import RenesasFlashProgrammer
from defs import MCU_Type, Comm_Mode


class R78K0Programmer(RenesasFlashProgrammer):
    ''' Class to program the 8-bit 78k0 MCUs '''


    def __init__(self, **kwargs):
        super().__init__(MCU_Type.R78K0, **kwargs)

        self.timeout = 1
        self.fl_block_size = 0x400

    def chk_return(self, cmd, ret):
        if not ret:
            return -1
        if ret[0] == 0x06:
            return 0
        return -1
