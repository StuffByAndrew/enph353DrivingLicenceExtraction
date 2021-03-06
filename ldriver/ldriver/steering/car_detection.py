import cv2
import rospy
import numpy as np
from sensor_msgs.msg import Image
from geometry_msgs.msg import Twist
from cv_bridge import CvBridge, CvBridgeError
from lane_detection import mask_rectangle
from pedestrian_detection import hsv_threshold, dilate_erode, function_counter
bridge = CvBridge()
"""
Car: 
lower: [0, 0, 105]
upper: [0, 0, 200]
"""
"""
Car wheels
Lower: [0,0,0]
Upper: [40,150,18]
"""
@function_counter
def car_motion_detection(current_image_input, previous_image, history):
    current_image = mask_rectangle(current_image_input, bottom=0.45, right=0.65)
    cv2.imshow('car', current_image)
    cv2.waitKey(1)
    current_image = hsv_threshold(current_image, lh=0, ls=0, lv=0, uh=40, us=150, uv=18)
    current_image = cv2.GaussianBlur(current_image, (21,21), 0)
    current_image = dilate_erode(current_image, 0, 5)

    if previous_image is None:
        previous_image = current_image
    difference = cv2.absdiff(current_image, previous_image)
    _, thresh = cv2.threshold(difference,55,255,cv2.THRESH_BINARY)
    previous_image = current_image
    history.append(np.count_nonzero(thresh))
    history.pop(0)
    average = sum(history)/len(history)
    return average, current_image
    
history = [10000 for _ in range(10)] 
previous_image = None
car_was_detected = False
def robot_can_move(current_image, threshold):
    global previous_image
    average, previous_image = car_motion_detection(current_image, previous_image, history) 
    car_is_detected = average < threshold
    cv2.imshow("Image", current_image)
    cv2.waitKey(1)
    return car_is_detected
    
def callback(image_data):
    global previous_image
    try:
        image = bridge.imgmsg_to_cv2(image_data, "bgr8")
    except CvBridgeError as e:
        print(e)
    #current_image = cv2.cvtColor(current_image_input, cv2.COLOR_BGR2GRAY)
    print(robot_can_move(image, 20))

def rotate_left(interval):
    command = Twist()
    command.angular.z = 0.62    
    move_pub.publish(command)
    rospy.sleep(interval)

if __name__ == "__main__":
    rospy.init_node("lane_following", anonymous=True)
    move_pub = rospy.Publisher("/R1/cmd_vel", Twist, queue_size=1)
    rospy.sleep(0.5)
    #rotate_left(1.5)
    image_sub = rospy.Subscriber("/R1/pi_camera/image_raw", Image, callback, queue_size=1)
    rate = rospy.Rate(0.5)
    while not rospy.is_shutdown():
        rate.sleep()