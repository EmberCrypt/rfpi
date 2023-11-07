import sys

from renesas_fpi import RenesasFlashProgrammer
from defs import Comm_Mode, MCU_Type


class V850Programmer(RenesasFlashProgrammer):
    ''' Class to program the V850 MCUs '''


    def __init__(self, **kwargs):
        super().__init__(MCU_Type.V850E2, **kwargs)


