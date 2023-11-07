import sys

from renesas_fpi import RenesasFlashProgrammer
from defs import Comm_Mode, MCU_Type


class R78K0RProgrammer(RenesasFlashProgrammer):
    ''' Class to program the 8-bit 78k0 MCUs '''


    def __init__(self, comm_mode, baud_rate = 9600):
        if comm_mode != Comm_Mode.UART1:
            logging.error("Please double check - 78k0r communication should be on TOOL0 (1-wire uart)")
            raise ValueError("Unsupported communication method")
        super().__init__(MCU_Type.R78K0R, comm_mode, baud_rate, 4)


