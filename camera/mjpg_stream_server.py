#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PIL import Image
import threading
from http.server import BaseHTTPRequestHandler,HTTPServer
from socketserver import ThreadingMixIn
from io import StringIO, BytesIO
import time
import cv2
import logging

class CamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.endswith('.mjpg'):
            self.send_response(200)
            self.send_header('Content-type','multipart/x-mixed-replace; boundary=--jpgboundary')
            self.end_headers()
            while True:
                try:
                    # frame = self.server.main.get_frame()
                    # if frame is not None:

                    #     imgRGB=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                    #     jpg = Image.fromarray(imgRGB)
                    #     tmpFile = BytesIO()
                    #     jpg.save(tmpFile,'JPEG')

                    tmpFile = self.server.main.get_img()

                    if tmpFile is not None:
                        self.wfile.write("--jpgboundary".encode())
                        self.send_header('Content-type','image/jpeg')
                        self.send_header('Content-length',str(tmpFile.getbuffer().nbytes))
                        self.end_headers()
                        self.wfile.write(tmpFile.getbuffer())

                    time.sleep(0.1)

                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(e)
                    raise e
            return
        elif self.path == '' or self.path == '/' or self.path.endswith('.html'):
            self.send_response(200)
            self.send_header('Content-type','text/html')
            self.end_headers()
            self.wfile.write('<html><head></head><body>'.encode())
            self.wfile.write('<img src="./cam.mjpg"/>'.encode())
            self.wfile.write('</body></html>'.encode())
            return


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""


class MjpgStreamServer:

    def __init__(self, host='0.0.0.0', port=8080):
        self._frame = None
        self._tmpFile = None

        self.server = ThreadedHTTPServer((host, port), CamHandler)
        self.server.main = self

        logging.info("server started http://%s:%s", host, port)

        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()

        self.mutex = threading.RLock()

    def get_frame(self):
        with self.mutex:
            return self._frame

    def set_frame(self, frame):
        with self.mutex:
            self._frame = frame
            self._tmpFile = None

    def get_img(self):
        with self.mutex:
            if self._tmpFile:
                return self._tmpFile

            if self._frame is not None:
                imgRGB=cv2.cvtColor(self._frame,cv2.COLOR_BGR2RGB)
                jpg = Image.fromarray(imgRGB)
                self._tmpFile = BytesIO()
                jpg.save(self._tmpFile,'JPEG')
                return self._tmpFile


if __name__ == '__main__':
    MjpgStreamServer()
    while 1:
        time.sleep(10)

