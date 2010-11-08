#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Just a simple wrapper for the Sparkfun Graphic LCD Serial Backpack (LCD-09352)

If you're planning on doing any extensive animation with this device, you better
understand that this device suffers from bad buffering problems; it only has 416
bytes of serial buffering on board and it doesn't block when it's full. So, if
you send this device data faster than it can draw, you'll lose data. To
compensate, adjust the heartbeat depending on the complexity of your
graphics. You can usually get the right values, it just takes a bit of tweaking.

If you're just doing text, you'll probably never have a problem, and in that case
you can turn off the buffering by setting buffer_size=0
"""
__author__ = "Ryan McGuire (ryan@enigmacurry.com)"
__date__   = "Sun Nov  7 13:51:13 2010"

import serial
import time
import threading
import cStringIO
import logging
import Queue

logging.basicConfig()
log = logging.getLogger("graphic_lcd")
log.setLevel(logging.INFO)
        
class LCD(threading.Thread):
    def __init__(self, port, baud, size=(128,64),
                 heartbeat=3, buffer_size=416):
        self.size = size
        self.__comm = serial.Serial(port,baud)
        self.__rows = (self.size[1] // 8)
        self.__cols = (self.size[0] // 6)
        self.heartbeat = heartbeat
        self.buffer_size = buffer_size
        self.__buffer = Queue.Queue(self.buffer_size) #Max data controller can buffer
        self.__stop = False
        threading.Thread.__init__(self)
    def run(self):
        #Send self.buffer_size bytes every heartbeat
        if(self.buffer_size == 0):
            #Don't bother buffering
            return 
        while True:
            start = time.time()
            for x in xrange(self.buffer_size):
                try:
                    d = self.__buffer.get(timeout=0.5)
                except Queue.Empty:
                    if self.__stop:
                        return
                    break
                log.debug("Writing from buffer: {0}".format(repr(d)))
                self.__comm.write(d)
            #Wait till the next heartbeat, which could have already passed.
            next_beat = self.heartbeat - (time.time() - start)
            if next_beat > 0:
                log.debug("Waiting {0} seconds for next heartbeat".format(next_beat))
                time.sleep(next_beat)
    def stop(self):
        self.__stop = True
    def send(self, data):
        """Send raw bytes to the controller

        This is put into a Queue to buffered by the running thread
        """
        if self.buffer_size > 0:
            log.debug("Placing in buffer: {0}".format(data))
            for x in data:
                self.__buffer.put(x)
        else:
            #Bypass buffer entirely
            log.debug("Writing (bypassing buffer): {0}".format(data))
            self.__comm.write(data)
    def type(self, text):
        """Type text to the screen

        Uses whatever the current cursor position is,
        use set_char_postion() to set it manually.
        """
        self.send(text)
    def init_display(self):
        """Initialize the display

        This cleans up the display from previous interaction. Unnecessary to run
        just after turning on the display.
        
        This does two things:
          * Sends some space characters to the display to clear out any command
            that was halfway completed.
          * Turns off the backlight
          * Clear the display
        """
        self.send("        ")
        self.set_backlight(0)
        self.clear()
    def clear(self):
        """Clear the screen"""
        self.send("|\x00")
    def demo(self):
        """Run the built-in demo sequence"""
        self.send("|\x04")
    def reverse(self):
        """Invert the colors of the screen"""
        self.send("|\x12")
    def set_backlight(self, percent):
        """Set the backlight level"""
        if percent < 0 or percent > 100:
            raise ValueError("Backlight percentage must be in range 0-100")
        self.send("|\x02"+chr(percent))
    def __set_pos_x(self,x):
        if x < 0 or x > self.size[0]:
            raise ValueError("X coordinate must be in range 0-{0}".format(self.size[0]))
        self.send("|\x18"+chr(x))
    def __set_pos_y(self,y):
        if y < 0 or y > self.size[1]:
            raise ValueError("Y coordinate must be in range 0-{0}".format(self.size[1]))
        self.send("|\x19"+chr(y))
    def set_pixel_position(self,x,y):
        """
        Set the cursor position in pixels
        
        Pixel positions start at the bottom left of the screen.
        set_pixel_position(0,0) - sets the cursor at far left bottom corner
        """
        self.__set_pos_x(x)
        self.__set_pos_y(y)
    def set_char_position(self,row,column):
        """
        Set the cursor position in characters.
        
        Character positions starts at the top left of the screen.
        set_char_position(0,10) - sets cursor on the 1st row, and 11th column
        """
        self.__set_row(row)
        self.__set_column(column)
    def __set_row(self,r):
        """Goto the character row r"""
        if r < 0 or r >= self.__rows:
            raise ValueError(
                "row number must be in range 0-{0}".format(self.__rows-1))
        self.__set_pos_y(((self.__rows - r) * 8) - 1)
    def __set_column(self,c):
        """Goto the character row c"""
        if c < 0 or c >= self.__cols:
            raise ValueError(
                "column number must be in range 0-{0}".format(self.__cols-1))
        self.__set_pos_x(c * 6)
    def pixel(self, x, y, draw=True):
        """
        Draw or clear a pixel at the coordinates x,y
        draw is boolean to draw or clear
        
        (Pixel positions start at the bottom left of the screen)
        """
        self.send("|\x10"+chr(x)+chr(y)+chr(int(draw)))
    def line(self, x1, y1, x2, y2, draw=True):
        """
        Draw or clear a line from the coordinates x1,y1 to x2,y2
        draw is boolean to draw or clear
        
        (Pixel positions start at the bottom left of the screen)
        """
        self.send("|\x0c"+chr(x1)+chr(y1)+chr(x2)+chr(y2)+chr(int(draw)))
    def box(self, x1, y1, x2, y2, draw=True):
        """
        Draw or clear a box from the coordinates x1,y1 to x2,y2
        draw is boolean to draw or clear

        BUG: Box clearing is documented in Sparkfun docs, but doesn't work on
        mine, so diabled for now :(
        
        (Pixel positions start at the bottom left of the screen)
        """
        #box clearing doesn't work on my unit, the last byte is interpreted as
        #a character to type on the screen. Disable box clearing for now:
        #self.send("|\x0f"+chr(x1)+chr(y1)+chr(x2)+chr(y2)+chr(int(draw)))

        self.send("|\x0f"+chr(x1)+chr(y1)+chr(x2)+chr(y2))
    def circle(self, x, y, r, draw=True):
        """
        Draw or clear a circle at the coordinates x,y with radius r
        draw is boolean to draw or clear
        
        (Pixel positions start at the bottom left of the screen)
        """
        self.send("|\x03"+chr(x)+chr(y)+chr(r)+chr(int(draw)))
    def erase(self, x1, y1, x2, y2):
        """
        Erase a block of the screen from coordinates x1,y1 to x2,y2.
        
        (Pixel positions start at the bottom left of the screen)
        """
        self.send("|\x05"+chr(x1)+chr(y1)+chr(x2)+chr(y2))


if __name__ == "__main__":
    #Just a test of my screen over bluetooth:
    lcd = LCD("/dev/rfcomm0",baud="115200",size=(128,64))
    lcd.start()
    lcd.init_display()
    lcd.set_backlight(50)
    while True:
        try:
            lcd.clear()
            lcd.type("Just a silly test...")
            for x in xrange(20,30,2):
                lcd.circle(x,x,10)
            for x in xrange(1,30,2):
                lcd.box(45,10,45+x,10+x)
            for x in xrange(1,30,2):
                lcd.line(80+x,10,80+x,40)
            for x in xrange(1,30,2):
                lcd.line(80,10+x,110,10+x)
            lcd.set_char_position(7,10)
            lcd.type("See ya :)")
            for x in xrange(0,128):
                lcd.line(x,0,x,63)
            for x in xrange(0,32):
                lcd.circle(64,32,x,False)
        except KeyboardInterrupt:
            log.warn("Flushing buffer and quitting...")
            lcd.init_display()
            lcd.stop()
            break
