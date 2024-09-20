import datetime
import time
import pyautogui

stop = False

# one window
x_coord = 656
y_coord = 989
# split window
# x_coord = 1593
# y_coord = 786

while not stop:
    curr = datetime.datetime.now()

    # check if its 9:00 AM or later, add some tolerance to ensure not clicking too early
    if curr.hour >= 7 and curr.minute >= 30 and curr.second >= 0 and curr.microsecond >= 4:
        # click on the enroll button
        pyautogui.click(x_coord, y_coord)
        if curr.second > 0:
            stop = True
    else:
        # wait 50 milliseconds
        time.sleep(0.1)
       
# time.sleep(5)
# # pyautogui.click(x_coord, y_coord)
# print(pyautogui.position())