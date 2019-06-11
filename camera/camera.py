#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import paho.mqtt.client
import click
import click_log
import logging
from collections import deque
from imutils.video import VideoStream
import numpy as np
import cv2
import imutils
import time
import sys
import json
import base64
import os
from .mjpg_stream_server import MjpgStreamServer

logging.basicConfig(format='%(asctime)s %(message)s')


def mqtt_on_connect(mqttc, userdata, flags, rc):
    logging.info('Connected to MQTT broker with code %s', rc)

    logging.debug('Subscribe: %s', "ronny/camera/foto/get")
    mqttc.subscribe('ronny/camera/foto/get')


def mqtt_on_disconnect(mqttc, userdata, rc):
    logging.info('Disconnect from MQTT broker with code %s', rc)


def mqtt_on_message(mqttc, userdata, message):
    logging.debug('Message %s %s', message.topic, message.payload)

    img = userdata['http'].get_img()

    with open("/run/user/1000/img.jpg", "wb") as outfile:
        outfile.write(img.getvalue())

    # foto = base64.b64encode(img.getvalue())

    # mqttc.publish('ronny/camera/foto', foto)


@click.command()
@click.option('--video', required=True, help='Video stream number', default=0, type=int)
@click.option('--fps', required=True, help='Video stream fps', default=10, type=int)
@click.option('--deque-len', required=True, help='Deque lenngth', default=10, type=int)
@click.option('--host', 'mqtt_host', type=click.STRING, default="127.0.0.1", help="MQTT host to connect to [default: 127.0.0.1].")
@click.option('--port', 'mqtt_port', type=click.IntRange(0, 65535), default=1883, help="MQTT port to connect to [default: 1883].")
@click.option('--imshow', is_flag=True, help="Show image over cv2.imshow.")
@click_log.simple_verbosity_option(default='INFO')
def run(video, fps, deque_len, mqtt_host, mqtt_port, imshow):
    logging.info("Process started")

    http = MjpgStreamServer()

    vs = VideoStream(src=video).start()

    minHSV = np.array([165, 132, 98])
    maxHSV = np.array([195, 255,  255])

    # minHSV = np.array([0, 137, 11])
    # maxHSV = np.array([5, 255,  255])

    pts = deque(maxlen=deque_len)
    counter = 0
    (dX, dY) = (0, 0)
    direction = ""


    path = os.path.realpath(os.path.dirname(__file__))
    face_cascade = cv2.CascadeClassifier(os.path.join(path, 'haarcascade_frontalface_default.xml'))
    eye_cascade = cv2.CascadeClassifier(os.path.join(path, 'haarcascade_eye.xml'))

    mqttc = paho.mqtt.client.Client(userdata={'http': http}) if mqtt_host else None

    if mqttc:
        mqttc.on_connect = mqtt_on_connect
        mqttc.on_disconnect = mqtt_on_disconnect
        mqttc.on_message = mqtt_on_message

        mqttc.connect(mqtt_host, mqtt_port, keepalive=10)
        mqttc.loop_start()

    time.sleep(2.0)

    logging.info('Loop start')
    while True:

        time.sleep(0.1)
        frame = vs.read()

        frame = imutils.resize(frame, width=600)

        # print(frame[200][200])
        # cv2.circle(frame,(200,200), 20, (255,0,0), 1)
        # cv2.imshow("frame", frame)

        blurred = cv2.GaussianBlur(frame, (11, 11), 0)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        for (x,y,w,h) in faces:
            cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
            # roi_gray = gray[y:y+h, x:x+w]
            # roi_color = frame[y:y+h, x:x+w]
            # eyes = eye_cascade.detectMultiScale(roi_gray)
            # for (ex,ey,ew,eh) in eyes:
            #     cv2.rectangle(roi_color,(ex,ey),(ex+ew,ey+eh),(255,0,0),2)

        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

        mask = cv2.inRange(hsv, minHSV, maxHSV)
        # cv2.imshow("mask", mask)

        mask = cv2.erode(mask, None, iterations=2)
        # cv2.imshow("erode", mask)
        mask = cv2.dilate(mask, None, iterations=2)
        # cv2.imshow("dilate", mask)

        cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = imutils.grab_contours(cnts)
        center = None
        radius = None
        publish = False

        if len(cnts) > 0:
            c = max(cnts, key=cv2.contourArea)
            ((x, y), radius) = cv2.minEnclosingCircle(c)
            M = cv2.moments(c)
            center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

            if radius > 10:
                cv2.circle(frame, (int(x), int(y)), int(radius), (0, 255, 255), 2)
                cv2.circle(frame, center, 5, (0, 0, 255), -1)

                for (x,y,w,h) in faces:
                    if x <= center[0] <= x + w and y <= center[1] <= y + h:
                        cv2.rectangle(frame,(x,y),(x+w,y+h),(0,255,0),2)

                        if len(pts) > 0 and pts[0] is not None:
                            if abs(pts[0][0] - center[0]) > 5 or abs(pts[0][1] - center[1]):
                                publish = True
                        break
                else:
                    center = None
            else:
                center = None

        pts.appendleft(center)

        for i in np.arange(1, len(pts)):

            if pts[i - 1] is None or pts[i] is None:
                continue

            if counter >= 10 and i == 1 and len(pts) > 9 and pts[-10] is not None:
                dX = pts[-10][0] - pts[i][0]
                dY = pts[-10][1] - pts[i][1]
                (dirX, dirY) = ("", "")

                if np.abs(dX) > 20:
                    dirX = "East" if np.sign(dX) == 1 else "West"

                if np.abs(dY) > 20:
                    dirY = "North" if np.sign(dY) == 1 else "South"

                if dirX != "" and dirY != "":
                    direction = "{}-{}".format(dirY, dirX)

                else:
                    direction = dirX if dirX != "" else dirY

            thickness = int(np.sqrt(deque_len / float(i + 1)) * 2.5)
            cv2.line(frame, pts[i - 1], pts[i], (0, 0, 255), thickness)

        cv2.putText(frame, direction, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 3)
        cv2.putText(frame, "dx: {}, dy: {}".format(dX, dY), (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

        if publish and mqttc:
            mqttc.publish("ronny/camera/object", json.dumps({"x": center[0], "y": center[1], "dx": dX, "dy": dY, "radius": radius}), qos=0)


        http.set_frame(frame)
        counter += 1

        if imshow:
            cv2.imshow("Frame", frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

    vs.stop()

    # cv2.destroyAllWindows()


def main():
    run()
    # try:
    #     run()
    # except KeyboardInterrupt:
    #     pass
    # except Exception as e:
    #     logging.error(e)
    #     sys.exit(1)


if __name__ == '__main__':
    main()
