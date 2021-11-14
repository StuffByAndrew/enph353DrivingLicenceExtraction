import cv2 
import numpy as np

"""for license plates:
uh = 0
us = 0
uv = 120
lh = 0
ls = 0
lv = 89

for road detection:
uh = 0
us = 0
uv = 95
lh = 0
ls = 0
lv = 75
"""
def hsv_threshold(img, lh, uh, ls, us, lv, uv):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    cv2.medianBlur(hsv,5)

    uh = 0
    us = 0
    uv = 120
    lh = 0
    ls = 0
    lv = 89
    lower_hsv = np.array([lh,ls,lv])
    upper_hsv = np.array([uh,us,uv])

    return cv2.inRange(hsv, lower_hsv, upper_hsv)

def display_hsv_threshold(image_file):
    cv2.imshow("HSV Threshold", hsv_threshold(image_file))
    cv2.waitKey(0)