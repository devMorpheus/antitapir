import os
import sys
import random
import base64

key = []

def code(data, pos):
    out = bytearray()
    index = pos
    for element in data:
        enc = element ^ key[index]
        out.append(enc)
        if index == 255:
            index = 0
        else:
            index = (index + 1) % 256

    return out

def encode(data):
    pos = random.randint(0, 255)
    out = code(data, pos)
    out.append(pos)
    return out


def decode(data):
    pos = data[len(data) - 1]
    data = data[:-1]
    out = code(data, pos)
    return out

def main():
    global key

    keyFile = 'key.bin'
    configFile = 'config.json'
    
    with open(keyFile, 'rb') as f:
        key = f.read()

    with open(configFile, 'rb') as f:
        read_data = f.read()
    
    data = encode(read_data)

    with open('config.bin', 'wb') as f:
        f.write(data)

main()
