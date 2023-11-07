from enum import Enum

class MCU_Type(Enum):
    """Which MCU type are we talking to"""
    V850E2  =   "v850e2"
    V850ES  =   "v850es"
    RH850   =   "rh850"
    R78K0   =   "78k0"      # For the 78K0 MCU
    R78K0_Kx2   =   "78k0_kx2"  # For tool reset
    RL78    =   "rl78"
    D76F    =   "d76f"
    R78K0R  =   "78k0r"     # For the 78K0R MCUs
    V850E   =   "v850e"
    R32C     =   "r32c"       # R8C/ R32C/ ...

class Comm_Mode(Enum):
    """Communication mode""" 
    SPI     =   "spi"
    UART2   =   "uart2"     # standard 2 wire UART
    UART1   =   "uart1"     # 1 wire UART such as on the 78K0R
    TOOLD   =   "toold"     # TOOLD (same as 1 wire UART but with a different entry sequence on TOOLC)
    TOOL0   =   "tool0"


class InvalidFrameError(ValueError):
    '''Invalid byte at the beginning of the frame'''
    pass

class InvalidHeaderError(ValueError):
    '''Invalid header byte'''
    pass

class InvalidFooterError(ValueError):
    '''Invalid footer byte'''
    pass

class InvalidChecksumError(ValueError):
    '''Checksum is wrong'''
    pass

class NoResponseError(ValueError):
    '''No response received'''
    pass

class NoAckError(ValueError):
    '''Message was received successfully but status was not ACK'''
    pass


