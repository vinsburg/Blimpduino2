#!/usr/bin/python3
from pynput.keyboard import Key, Listener
import socket
import threading
import time
from collections import defaultdict
import numpy as np


def s_int16_to_bytes(int16):
    return int16.to_bytes(length=2, byteorder='big', signed=True)
si2b = s_int16_to_bytes


def bytes_to_s_int16(bytez):
    return int.from_bytes(bytes=bytez, byteorder='big', signed=True)


class blimpPubUDP:
    def __init__(self, PUDP_IP="192.168.4.1", PUDP_PORT=2222, *args, **kwargs):
        _, _ = args, kwargs
        self.PUDP_IP = PUDP_IP
        self.PUDP_PORT = PUDP_PORT
        self.sock = socket.socket(
                socket.AF_INET, # Internet
                socket.SOCK_DGRAM, # UDP
        )
    def pub(self, msg):
        self.sock.sendto(msg, (self.PUDP_IP, self.PUDP_PORT))


class blimpState:
    def __init__(self,):
        self.ch2byte_map = {}
        self.default_val=b'\x00\x00'
        self.ch2byte_map[0]=b'JJBA' # for reverse kinematics control, or b'JJBM' for manual control
        for ind in range(1,9):
            self.ch2byte_map[ind]=self.default_val

    def update_chan(self, ch_byte_ind, value):
        if ch_byte_ind in self.ch2byte_map:
            self.ch2byte_map[ch_byte_ind]=value
    
    def get_message(self,):
        return b''.join([self.ch2byte_map[ind] for ind in range(len(self.ch2byte_map))])


class blimpKeyMachine:
    def __init__(self, period_time_in_secs=0.05, *args, **kwargs):
        self.key2channel_map = {
            'w': (1, si2b(500)), 's': (1, si2b(-500)),
            'a': (2, si2b(500)), 'd': (2, si2b(-500)),
            'q': (3, si2b(20)), 'e': (3, si2b(-20)),
            'm': (0, b'JJBM'), 'n': (0, b'JJBA'),
            '0': (5, si2b(0)), '1': (5, si2b(1)), '2': (5, si2b(2)), '3': (5, si2b(3)),
            '9': (5, si2b(100)), 
        }
        self.state = blimpState()
        self.pubber = blimpPubUDP(*args, **kwargs)
        self.null_return_value = None
        self.period_time_in_secs = period_time_in_secs
        self.last_release_time=defaultdict(float)
        self.waiting_for_release=set()

    def on_press(self, key):
        if self.is_valid_key(key):  
            # print('{0} pressed'.format(key))
            keychar = key.char.lower()
            chan, val = self.key2channel_map[keychar]
            self.state.update_chan(chan, val)

    def on_release(self, key):
        if key == Key.esc:
                return False # Stop listener
        if self.is_valid_key(key):
            keychar = key.char.lower()
            chan, _ = self.key2channel_map[keychar]
            if chan not in [0,5]: 
                # 0 & 5 are mode switch channels, key release is meaningless
                self.last_release_time[keychar]=time.time()
                self.waiting_for_release.add(keychar)

    def update_state_with_key_releases(self):
        if not len(self.waiting_for_release):
            return
        now = time.time()
        deletion_queue = []
        for keychar in self.waiting_for_release:
            if now-self.last_release_time[keychar] > 2*self.period_time_in_secs:
                # enough time passed since the key was released
                chan, _ = self.key2channel_map[keychar]
                self.state.update_chan(chan, self.state.default_val)
                deletion_queue.append(keychar)
        for keychar in deletion_queue:            
            self.waiting_for_release.remove(keychar)
    
    def is_valid_key(self, key):
        return hasattr(key, 'char') and key.char in self.key2channel_map

    def cycle_pub(self):
        while True:
            self.update_state_with_key_releases()
            self.pubber.pub(self.state.get_message())
            time.sleep(self.period_time_in_secs)
    
    def run_main(self):
        cycle = threading.Thread(target=self.cycle_pub, daemon=True)
        listener = Listener(on_press=self.on_press, on_release=self.on_release)
        listener.start()
        cycle.start()
        listener.join()

def print_intro():
    print('''_____________________________________________________
Welcome to the Blimpduino keyboard controller, Press:
    "W" or "S" to move forward or backwards
    "A" or "D" to turn left or right
    "Q" or "E" to go up or down
    "M" or "N" to go to "Manual" or "Reverse kinematics mode"
    "Numbers 0,1,2,3 and 9 for Modes:
           Mode 0=> manual,
           Mode 1=> Manual control with altitude hold
           Mode 2=> Yaw stabilization
           Mode 3=> Yaw stabilization with altitude hold
           Mode 9=> Stop motors
    "Esc" to exit
    
Connect your PC to network "JJRobots_XX" with password "87654321" before running this script''')

if __name__=='__main__':
    print_intro()
    blimp = blimpKeyMachine(
        period_time_in_secs=0.05,
        PUDP_IP="127.0.0.1",
        # PUDP_IP="192.168.4.1",
    )
    blimp.run_main()
    
