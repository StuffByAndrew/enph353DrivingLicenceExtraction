#!/usr/bin/env python2
from __future__ import print_function

import cv2
import time
import rospy
import numpy as np
from sensor_msgs.msg import Image
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, Int16, String
from cv_bridge import CvBridge, CvBridgeError
from ldriver.steering.car_detection import robot_can_move, car_motion_detection
from ldriver.steering.lane_detection import right_roadline_center, horizontal_distance_from_line
from ldriver.steering.pedestrian_detection import pedestrian_crossing
from ldriver.steering.road_detection import detect_gl
from ldriver.steering.lane_detection import slope
from scoring import format_message

bridge = CvBridge()

class Steering_Control:
    def __init__(self, base_speed, KP, target_line, move_pub):
        self.base_speed = base_speed
        self.KP = KP
        self.target_line = target_line
        self.move_pub = move_pub
        
    def get_error(self, point):
        error = horizontal_distance_from_line(point, *self.target_line)
        return self.KP*error
    
    def auto_steer(self, image):
        centroid = right_roadline_center(image)
        error = self.get_error(centroid)
        command = Twist()
        command.linear.x = self.base_speed
        command.angular.z = error
        self.move_pub.publish(command)
    
    def move_forwards(self, duration):
        command = Twist()
        command.linear.x = 0.5
        self.move_pub.publish(command)
        rospy.sleep(duration)
    
    def slow_stop(self, start_speed, end_speed, interval, decrements):
        speed_decrement = (start_speed - end_speed) / decrements
        time_interval = interval / decrements
        command = Twist()
        for _ in range(decrements):
            command.linear.x = start_speed - speed_decrement
            self.move_pub.publish(command)
            rospy.sleep(time_interval)
    
    def turn_left(self, interval):
        command = Twist()
        command.linear.x = 0.19
        command.angular.z = 0.62    
        self.move_pub.publish(command)
        rospy.sleep(interval)
        self.slow_stop(0.2,0,1,5)
    
    def stop(self):
        self.move_pub.publish(Twist())

class Pedestrian_Detection:
    def __init__(self, threshold, history_length, ignore=8):
        self.threshold = threshold
        self.history_length = history_length
        self.ignore = ignore
        self.previous_image = None
        self.pedestrian_was_crossing = False
        self.history = [0 for _ in range(history_length)]

    def robot_should_cross(self, current_image):
        running_average, self.previous_image = pedestrian_crossing(current_image, self.previous_image, self.history)

        if pedestrian_crossing.calls <= self.ignore:
            running_average = 0
            self.history = [0 for _ in range(self.history_length)]
            
        pedestrian_currently_crossing = running_average > self.threshold
        #---------------------
        if pedestrian_currently_crossing: rospy.logdebug("currently moving: {}, {}".format(running_average, self.history))
        else: rospy.logdebug("not moving: {}, {}".format(running_average, self.history))
        #---------------------
        if not pedestrian_currently_crossing and self.pedestrian_was_crossing:
            pedestrian_crossing.calls = 0
            self.pedestrian_was_crossing, self.previous_image = False, None
            self.history = [0 for i in range(self.history_length)]
            return True
        else:
            self.pedestrian_was_crossing = pedestrian_currently_crossing
            return False

class Car_Detection:
    def __init__(self, threshold, history_length, ignore=3):
        self.threshold = threshold
        self.history_length = history_length
        self.ignore = ignore
        self.previous_image = None
        self.car_was_detected = False
        self.history = [0 for _ in range(history_length)]
        self.was_over = False
    
    def robot_can_move(self, current_image):
        # average, self.previous_image = car_motion_detection(current_image, self.previous_image, self.history) 
        # print(average)
        # car_is_detected = average > self.threshold
        # if not car_is_detected and self.car_was_detected:
        #     self.car_was_detected, self.previous_image = False, None
        #     self.history = [10000 for _ in range(self.history_length)]
        #     return True
        # else:
        #     self.car_was_detected = car_is_detected
        #     return False
        average, self.previous_image = car_motion_detection(current_image, self.previous_image, self.history)
        if car_motion_detection.calls <= self.ignore: 
            average = 0
            self.history = [0 for _ in range(self.history_length)]
        can_move = self.was_over and average == 0
        #---------------
        # copy = self.previous_image.copy()
        # cv2.putText(copy, str(can_move), (20,30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
        # cv2.putText(copy, str(average), (20,60), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
        # cv2.imshow("Image", copy)
        # cv2.waitKey(1)
        #--------------
        if can_move:
            self.was_over = False
            return True
        elif not self.was_over:
            self.was_over = average > self.threshold
        return False
        

class HardTurner:
    def __init__(self, move_pub):
        self.move_pub = move_pub
        self.aligning = False
        self.cv_bridge = CvBridge()
        self.last_line = 1.0
        self.lost_dur = 0

    def left_turn(self):
        command = Twist()
        command.linear.x = 0.35 # 0.22
        command.angular.z = 1.05 # 0.8  
        self.move_pub.publish(command)
        rospy.sleep(1.5)
        self.stop()

    def stop(self):
        self.move_pub.publish(Twist())

    def right_turn(self):
        command = Twist()
        command.linear.x = 0.35 # 0.185
        command.angular.z = -1.06 # -0.62
        self.move_pub.publish(command)
        rospy.sleep(1.5)
        self.stop()

    def straight(self, dur):
        command = Twist()
        command.linear.x = 0.3
        self.move_pub.publish(command)
        rospy.sleep(dur)
        self.stop()

    def twist(self, dir, dur):
        command = Twist()
        command.angular.z = dir
        self.move_pub.publish(command)
        rospy.sleep(dur)
        self.stop()

    def back(self, dur, speed=0.3):
        command = Twist()
        command.linear.x = -speed
        self.move_pub.publish(command)
        rospy.sleep(dur)
        self.stop()

    def align(self):
        def aligning(data):
            img = self.cv_bridge.imgmsg_to_cv2(data, "bgr8")
            line, threshed = detect_gl(img)
            h = threshed.shape[0]
            # cv2.imshow('testing', threshed)
            # cv2.waitKey(1)
            print(line)
            if not len(line):
                self.lost_dur += 1
                if self.lost_dur > 10:
                    self.back(0.1, speed=0.08)
                return
            s = slope([line])
            self.lost_dur = 0 
            print(s)
            command = Twist()
            if np.isclose(0.0, s, atol=0.01):
                mean_y = np.mean([line[1], line[3]])
                if mean_y < 9*h//10:
                    command.linear.x = 0.08
                elif np.isclose(self.last_line, s):
                    self.image_sub.unregister()
                    self.aligning = False
                    print('aligned')
            elif s > 0:
                command.angular.z = -0.2 #0.13 
            elif s < 0:
                command.angular.z = 0.2
            self.last_line  = s
            self.move_pub.publish(command)
        
        self.aligning = True
        self.image_sub = rospy.Subscriber("/R1/pi_camera/image_raw2", Image, aligning, queue_size=1)
        while self.aligning:
            rospy.sleep(1)
    
    def face_inwards(self):
        self.straight(0.2)
        self.align()
        self.straight(0.35)
        self.left_turn()
        self.back(0.4)
        self.align()
    
    def execute_hardturn(self):
        # P7
        self.left_turn()
        self.straight(0.18)
        self.right_turn()
        self.stop()
        self.back(0.8)
        self.twist(dir=0.45, dur=0.2)
        # P8
        self.straight(2.1)
        self.right_turn()
        self.twist(dir=-0.5, dur=0.2)
        self.straight(1.5)
        self.align()
        self.right_turn()
        self.twist(dir=-0.5, dur=0.3)
        self.straight(0.3)
        # Back Outside
        self.left_turn()
        timer_pub.publish(end_msg)
        self.back(0.2)
        self.left_turn()
        self.back(1.2)

class Detection:
    def __init__(self):
        self.detected = None
        self.duration = 0
        self.count = 0

def update_redline(detection):
    if detection.data:
        Redline.detected = True
    else:
        Redline.detected = False

def update_greenline(detection):
    if detection.data:  
        Greenline.detected = True
    else:
        Greenline.detected = False

cache = [0 for _ in range(5)]
def update_license_number(detection):
    cache.append(detection.data)
    cache.pop(0)
    if detection.data == 1 and LicenseNumber.detected != 1:
        Lap.count += 1
    if detection.data == LicenseNumber.detected:
        LicenseNumber.duration += 1
    else:
        LicenseNumber.duration = 0
    LicenseNumber.detected = detection.data

def autopilot(image_data):
    try:
        image = bridge.imgmsg_to_cv2(image_data, "bgr8")
    except CvBridgeError as e:
        print(e)
    #########################################
    # text = "LicenseNumber:{}, Duration:{}, Greenline:{}, Innerloop:{}".format(
    #     LicenseNumber.detected == 1,
    #     LicenseNumber.duration > 0,
    #     Greenline.detected,
    #     not Innerloop.detected
    # )
    # cv2.putText(image, str(cache), (20,30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
    # cv2.putText(image, text, (20,60), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
    # cv2.imshow("image", image)
    # cv2.waitKey(1)
    #########################################
    if Redline.detected:
        Steering.stop()
        if Pedestrian.robot_should_cross(image):
            rospy.logdebug("Robot Crossing.\n-----------------------")
            Steering.move_forwards(1.25)
            Redline.was_detected = False
    elif LicenseNumber.detected == 1 \
        and LicenseNumber.duration > 1 \
            and Greenline.detected \
                and not Innerloop.detected \
                    and Lap.count >= -1:
        Innerloop.detected = True
    else:
        if Innerloop.detected:
            if not Aligned.detected:
                Steering.stop()
                ht.face_inwards()
                Aligned.detected = True
            elif Car.robot_can_move(image): 
                ht.execute_hardturn()
                Innerloop.detected = False
                Aligned.detected = False
        else:
            Steering.auto_steer(image)
    

if __name__ == "__main__":
    rospy.init_node("autopilot", log_level=rospy.DEBUG)
    move_pub = rospy.Publisher("/R1/cmd_vel", Twist, queue_size=1)
    ht = HardTurner(move_pub)

    Steering = Steering_Control(0.28, 0.02, (0.6228, -44), move_pub) # good: 0.23, Kp: 0.015
    Pedestrian = Pedestrian_Detection(200, 3)
    Redline = Detection()
    Greenline = Detection()
    LicenseNumber = Detection()
    Aligned = Detection()
    Car = Car_Detection(100, 5)
    Innerloop = Detection()
    Lap = Detection()

    start_msg, end_msg = String(), String()
    start_msg.data, end_msg.data = format_message(0,"0000"), format_message(-1,"0000")
    timer_pub = rospy.Publisher("/license_plate", String, queue_size=1)
    rospy.sleep(0.5)
    timer_pub.publish(start_msg)

    Steering.turn_left(3)
    
    image_sub = rospy.Subscriber("/R1/pi_camera/image_raw", Image, autopilot, queue_size=1)
    redline_sub = rospy.Subscriber("/redline", Bool, update_redline, queue_size=1)
    greenline_sub = rospy.Subscriber("/RoadDetection/greenline", Bool, update_greenline, queue_size=1)
    parking_number_sub = rospy.Subscriber("license_id", Int16, update_license_number, queue_size=1)
    
    rate = rospy.Rate(0.5)
    while not rospy.is_shutdown():
        rate.sleep()