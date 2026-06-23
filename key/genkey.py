import os
import sys
import random

def main():
    key = []
    for i in range(256):
        key.append(random.randint(0, 255))

    keyStr = ""
    keyStr += "key = [\n"
    for row in range(16):
        keyStr += '    '
        for column in range(16):
            keyStr += f'0x{key[(row*16) + column]:02x}, '
        keyStr += '\n'
    keyStr += "]"
    
    with open('key.py', 'w') as f:
        f.write(keyStr)

    with open('key.bin', 'wb') as f:
        f.write(bytearray(key))


main()
