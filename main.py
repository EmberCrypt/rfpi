import argparse
import logging
from enum import Enum
from time import sleep

from defs import MCU_Type, Comm_Mode
from flashcomm import RenesasFlashComm
from renesas_fpi import RenesasFlashProgrammer
from error import *

from rh850_prog import RH850Programmer
from r32c_prog import R32CProgrammer
from r78k0_prog import R78K0Programmer
from r78k0r_prog import R78K0RProgrammer
from v850e2_prog import V850Programmer
from rl78_prog import RL78Programmer

class Actions(Enum):
    RESET       =   "reset"
    PROGRAM     =   "program"
    VERIFY      =   "verify"
    ERASE       =   "erase"
    MCU_ON      =   "mcu_on"
    MCU_OFF     =   "mcu_off"
    READ        =   "read"
    TEST        =   "test"
    SIG         =   "sig"
    CHKS        =   "chks"
    CHK         =   "chk"
    RFO         =   "rfo"
    WFO         =   "wfo"



flash_programmers = {
        MCU_Type.RH850: RH850Programmer,
        MCU_Type.R32C: R32CProgrammer,
        MCU_Type.R78K0: R78K0Programmer,
        MCU_Type.R78K0_Kx2: R78K0Programmer,
        MCU_Type.R78K0R: R78K0RProgrammer,
        MCU_Type.V850E2: V850Programmer, 
        MCU_Type.RL78: RL78Programmer
        }

log = {
        "info": logging.INFO,
        "debug": logging.DEBUG
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Renesas Flash Programming', formatter_class=argparse.ArgumentDefaultsHelpFormatter)


    parser.add_argument("mcu", help="Specify the exact renesas MCU", choices = [t.value for t in MCU_Type])
    parser.add_argument("mode", help="The communication protocol", choices = [t.value for t in Comm_Mode], default="uart2")
    ''' Bootloader communication options '''
    parser.add_argument("--port", help="The serial device to be used", default = "/dev/ttyAMA0")
    parser.add_argument("--baud", help="The communication baud rate", type = int, default = 9600)
    parser.add_argument("--gpio_reset", help="The GPIO pin used for the reset pin", type = int, default = 3)
    parser.add_argument("--gpio_flmd", help="The GPIO pin used for the flmd pin", type = int, default = 2)

    parser.add_argument("--log_level", help="Logging level", choices = [k for k in log], default = "debug")

    
    ''' For specific commands '''
    subparsers = parser.add_subparsers(help = "Specific command to execute", dest = "command")
    ''' Simple parsers (require no args) '''
    subparsers.add_parser(Actions.RESET.value, help = "Initialises the bootloader interface")
    subparsers.add_parser(Actions.RFO.value, help = "Reads the flash options")
    subparsers.add_parser(Actions.WFO.value, help = "Writes the flash options") # TODO get input
    subparsers.add_parser(Actions.SIG.value, help = "Gets the silicon signature")
    subparsers.add_parser(Actions.MCU_ON.value, help = "Runs the MCU in normal mode (pulls RESET high and FLMD low")
    subparsers.add_parser(Actions.MCU_OFF.value, help = "Turns off the MCU (pulls RESET and FLMD low)")


    ''' Parsers requiring address '''
    parser_prog = subparsers.add_parser(Actions.PROGRAM.value, help = "Erases the memory and programs the given firmware")
    parser_prog.add_argument("addr", type = lambda x: int(x, 16), help = "address to program data at")
    parser_prog.add_argument("firmware", help = "The firmware to be programmed")

    parser_verify = subparsers.add_parser(Actions.VERIFY.value, help = "Verifies the given firmware")
    parser_verify.add_argument("addr", type = lambda x: int(x, 16), help = "address to verify data at")


    parser_erase = subparsers.add_parser(Actions.ERASE.value, help = "Erases the memory")
    parser_erase.add_argument("addr", type = lambda x: int(x, 16), help = "First address to be erased")


    parser_read = subparsers.add_parser(Actions.READ.value, help = "Read out part of the firmware")
    parser_read.add_argument("addr", type = lambda x: int(x, 16), help = "The address to read from")
    parser_read.add_argument("size", type = lambda x: int(x, 16), help = "The number of bytes to read")
    parser_read.add_argument("f_out", help = "The file the firmware is written to")

    parser_test = subparsers.add_parser(Actions.TEST.value, help = "Test a certain command")
    parser_test.add_argument("cmd", type = lambda x: int(x, 16), help = "The command to execute")
    parser_test.add_argument("cmd_args", help="The arguments of the test command", nargs=argparse.REMAINDER, default = []) 

    parser_chk = subparsers.add_parser(Actions.CHK.value, help = "Get a single checksum of the firmware")
    parser_chk.add_argument("addr_start", type = lambda x: int(x, 16), help = "The start address of the checksums")
    parser_chk.add_argument("addr_end", type = lambda x: int(x, 16), help = "The end address of the checksums")

    parser_chks = subparsers.add_parser(Actions.CHKS.value, help = "Get the checksums of the firmware")
    parser_chks.add_argument("addr_start", type = lambda x: int(x, 16), help = "The start address of the checksums")
    parser_chks.add_argument("addr_end", type = lambda x: int(x, 16), help = "The end address of the checksums")

    args = parser.parse_args() 

    mcu = MCU_Type(args.mcu)
    mode = Comm_Mode(args.mode)

    # Set logging level
    logging.basicConfig(level=log[args.log_level], format="%(filename)s:%(funcName)s: %(message)s")

    # kwargs = {"comm_mode": mode, "baud_rate": args.baud, "ser_port": args.port, "gpio_flmd": args.gpio_flmd, "gpio_reset": args.gpio_reset}

    # Create the flashcomm device
    flashcomm = RenesasFlashComm(mcu, mode, port = args.port, baud_rate = args.baud, gpio_flmd = args.gpio_flmd, gpio_reset = args.gpio_reset)

    kwargs = {"flashcomm": flashcomm}

    f_p = flash_programmers.get(mcu, RenesasFlashComm)(**kwargs)

    cmd = Actions(args.command)

    # check which command given
    if cmd == Actions.RESET:
        f_p.reset()
    elif cmd == Actions.PROGRAM:
        f_p.reset()
        f_p.flash(args.addr, args.firmware)
    elif cmd == Actions.READ:
        f_p.reset()
        _firm = f_p.read(args.addr, args.size)
        with open(args.f_out, "wb") as f:
            f.write(_firm)
    elif cmd == Actions.SIG:
        f_p.reset()
        f_p.get_signature()
    elif cmd == Actions.RFO:
        f_p.reset()
        f_p.rfo()
    elif cmd == Actions.WFO:
        f_p.reset()
        f_p.wfo()
    elif cmd == Actions.CHKS:
        f_p.reset()
        f_p.get_checksums(args.addr_start, args.addr_end)
    elif cmd == Actions.CHK:
        f_p.reset()
        f_p.get_checksum(args.addr_start, args.addr_end)
    elif cmd == Actions.TEST:
        while 1:
            try:
                f_p.reset()
                break
            except ValueError as e:
                pass
        f_p.test_cmd(args.cmd, [int(a, 16) for a in args.cmd_args])

    elif cmd == Actions.VERIFY:
        f_p.reset()
        f_p.verify(args.addr, [i & 0xff for i in range(0x100)])
    elif cmd == Actions.ERASE:
        f_p.reset()
        f_p.block_erase(args.addr)
    elif cmd == Actions.MCU_ON:
        flashcomm.mcu_on()
        while 1:
            pass
    elif cmd == Actions.MCU_OFF:
        flashcomm.mcu_off()
        while 1:
            pass
    

