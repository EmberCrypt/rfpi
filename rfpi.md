# Renesas Flash Programming Interface
All handy commands you should know about the Renesas Flash Programming Interface

## V850 

### On-Chip Debug
Works with a 95-bit ID code. Stored on FF470000-FF47000B. If all FF, then OCD enabled without hassle. Bit 0 on FF470000 indicates OCD enable / disable - set to 1 to enable. (Addresses are taken from V850E2/Fx4-L so could differ)

### V850E2/Dx4 - vw-ic

#### Signature
Addresses are in little endian (so swap bytes around) 
- Device data: 10  00  01  
- Micro: 44  37  30  46  33  35  32  36  20  20  
- Code flash end: ff  ff  2f  00
- Data flash end: ff  7f  00  02  
- Firmware version: 04  00  00


| Command | Hex | Params | Response | Comment |
| ------- | --- | ------ | -------- | ------- |
| Security get | A1 | | CB 13 00 00 FF 02 | (V850E2/Dx3)|
| Security get | A1 | | CB 01 00 00 17 00 | (v850E2/Fx4-L) |
| Security get | A1 | | DB 03 00 00 00 00 | (v850E2/Fx4-L) |
| Get flash params? | AA |  | | Security Denied | |
| Set ID code | A6 | ID Code - 0xC bytes| Security Denied | Id code sent after first ACK received in data frame |
| ? | A7 | | Security Denied | From CS+ when trying to download |
| Set Option byte | A9 | 00 00 00 80 | Security denied | Option byte is 0x80000000 so in reverse order (sent as data frame) |
| Block Blank Check | 32 | 00 00 00 00 00 0b ff ff | 1b (not blank) | Params given in command frame |
| Security Set | A0 | SEC\_BYTE 03 00 00 00 00 | 10 | bits 1,2,4,5 of SEC\_BYTE indicate some sec level. 03 is the boot block cluster last block number - not sure if relevant. The zeros are the reset vector addr |

## RH850
This is the latest version of the V850 core - fully backwards compatible. These chips can lock the bootloader as well as the readout protection. Bit of a pain. 


### RH850/F1x
! Only goes through the whole sequence @5V ! 

Cmd sequence:

| Debugger | Chip |
| -------- | ---- |
| 00 * 30 | 00 |
| 55 | C1 |
| 01 00 01 38 c7 03 | 81 00 01 38 C7 03 |
| 81 00 01 38 c7 03 | 81 00 19 38 10 ff 40 00 48 00 00 01 6e 36 00 00 7a 12 00 04 c4 b4 00 01 7d 78 40 35 03 |
| Then set frequency in IDE | |
| 01 00 09 32 00 f4 24 00 04 c4 b4 00 31 03 | 81 00 01 32 cd 03 |
| 81 00 01 32 cd 03 | 81 00 09 32 04 c4 b4 00 02 62 5a 00 8b 03 |
| 01 00 05 34 00 00 25 80 22 03 | 81 00 01 34 cb 03 |
| 01 00 01 00 ff 03 | 81 00 01 00 ff 03 |
| 01 00 01 2c d3 03 | 01 00 01 2c d3 03 |
| 81 00 01 2c d3 03 | 01 00 02 2c ff d3 03 |



Possible commands

| Byte | Command | Args | Comment |
| ---- | ------- | ---- | ------- |
| 3a | Sig get | none | Replies with 3b ...|
| 15 | Read | S3 S2 S1 S0 E3 E2 E1 E0 | For receive first frame: sends 81 00 01 15 ... , second frame onwards 01 00 01 15 |
| 27 | ? | none | No idea - replies with 8f ff 67 3a ff ... ff  (0x21 bytes) |
| 23 | ? | none | No idea - all ff |


### RH850 Frequency set

on a RH850/D2 (chk in parentheses)
**34 command still in same baud rate**

-  16Mhz & 115200: 
```
32 00 f4 24 00 07 27 0e 00 (71)
34 00 01 c2 00 (04) 
```

- 8Mhz & 115200:
```
32 00 7a 12 00 07 27 0e 00 (fd)
```

**Command 34 sets baud rate!!**




