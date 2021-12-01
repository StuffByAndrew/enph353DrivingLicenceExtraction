import cv2
import time
import rospy
import numpy as np
from sensor_msgs.msg import Image
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, Int16
from cv_bridge import CvBridge, CvBridgeError
from ldriver.steering.lane_detection import right_roadline_center, horizontal_distance_from_line
from ldriver.steering.pedestrian_detection import pedestrian_crossing
from ldriver.steering.hard_turning import HardTurner
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
        #--------------------------
        cv2.circle(image, centroid, 10, 255, -1)
        cv2.imshow("image", image)
        cv2.waitKey(3)
        #--------------------------
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
        command.linear.x = 0.2
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

class Detection:
    def __init__(self):
        self.detected = None

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

def update_license_number(detection):
    LicenseNumber.detected = detection.data

def autopilot(image_data):
    try:
        image = bridge.imgmsg_to_cv2(image_data, "bgr8")
    except CvBridgeError as e:
        print(e)
    #-------
    if Redline.detected:
        Steering.stop()
        if Pedestrian.robot_should_cross(image):
            rospy.logdebug("Robot Crossing.\n-----------------------")
            Steering.move_forwards(1.25)
            Redline.was_detected = False
    elif LicenseNumber.detected == 1 and Greenline.detected:
        Steering.move_forwards(.5)
        Steering.stop()
        ht.align()
        ht.straight(0.2)
        ht.left_turn()
        ht.back(0.4)
        ht.align()
        ht.left_turn()
        ht.straight(0.25)
        ht.right_turn()
        ht.straight(1.5)
        ht.right_turn()
        ht.straight(1.5)
        ht.align()
        ht.right_turn()
        ht.left_turn()
        ht.back(0.2)
        ht.left_turn()
        ht.back(1)
    else:
        Steering.auto_steer(image)

if __name__ == "__main__":
    rospy.init_node("autopilot", anonymous=True)
    move_pub = rospy.Publisher("/R1/cmd_vel", Twist, queue_size=1)
    ht = HardTurner()
    Steering = Steering_Control(0.20, 0.015, (0.6228, -44), move_pub)
    Pedestrian = Pedestrian_Detection(200, 3)
    Redline = Detection()
    Greenline = Detection()
    LicenseNumber = Detection()
    
    rospy.sleep(0.5)
    Steering.turn_left(3)
    
    image_sub = rospy.Subscriber("/R1/pi_camera/image_raw", Image, autopilot, queue_size=1)
    redline_sub = rospy.Subscriber("/redline", Bool, update_redline, queue_size=1)
    greenline_sub = rospy.Subscriber("/RoadDetection/greenline", Bool, update_greenline, queue_size=1)
    parking_number_sub = rospy.Subscriber("license_id", Int16, update_license_number, queue_size=1)
    
    rate = rospy.Rate(0.5)
    while not rospy.is_shutdown():
        rate.sleep()