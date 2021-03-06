import cv2
import numpy as np

def sharpen(img):
    sharp_k = np.array([[0, -1, 0],
                        [-1, 5,-1],
                        [0, -1, 0]])
    return cv2.filter2D(src=img, ddepth=-1, kernel=sharp_k)

#################################################
# Inspired by https://stackoverflow.com/questions/55149171/how-to-get-roi-bounding-box-coordinates-with-mouse-clicks-instead-of-guess-che
#################################################
# Edits made: 
# - added cache for undoing
# - made display part of
# - took image as in init arg instead of reading from file
#################################################
class BoundingBoxWidget(object):
    def __init__(self, image):
        self.original_image = image
        self.clone = self.original_image.copy()

        cv2.namedWindow('image')
        cv2.setMouseCallback('image', self.extract_coordinates)

        # Bounding box reference points
        self.image_coordinates = []
        self.cache = []

    def extract_coordinates(self, event, x, y, flags, parameters):
        # Record starting (x,y) coordinates on left mouse button click
        if event == cv2.EVENT_LBUTTONDOWN:
            self.image_coordinates = [(x,y)]

        # Record ending (x,y) coordintes on left mouse button release
        elif event == cv2.EVENT_LBUTTONUP:
            self.image_coordinates.append((x,y))
            print('top left: {}, bottom right: {}'.format(self.image_coordinates[0], self.image_coordinates[1]))
            print('x,y,w,h : ({}, {}, {}, {})'.format(self.image_coordinates[0][0], self.image_coordinates[0][1], self.image_coordinates[1][0] - self.image_coordinates[0][0], self.image_coordinates[1][1] - self.image_coordinates[0][1]))

            # Draw rectangle
            self.cache.append(self.clone) 
            cv2.rectangle(self.clone, self.image_coordinates[0], self.image_coordinates[1], (36,255,12), 2)
            cv2.imshow("image", self.clone) 

        # Clear drawing boxes on right mouse button click
        elif event == cv2.EVENT_RBUTTONDOWN:
            self.clone = self.original_image.copy()

    def show_image(self):
        return self.clone

    def display(self):
        while True:
            cv2.imshow('image', self.show_image())
            key = cv2.waitKey(1)

            # Close program with keyboard 'q'
            if key == ord('q'):
                cv2.destroyAllWindows()
                exit(1)
            elif key == ord('z'):
                self.clone = self.cache.pop()

if __name__ == '__main__':
    boundingbox_widget = BoundingBoxWidget()
    boundingbox_widget.display()
    