import cv2
import os
Class_Name1 = "crack"
Class_Name2 = "no_crack"
path1 = f"dataset/{Class_Name1}"
path2 = f"dataset/{Class_Name2}"
os.makedirs(path1,exist_ok =True)
os.makedirs(path2,exist_ok =True)
cap=cv2.VideoCapture(1)
print('''S To save Cracked A to save no
      crack and Q to Exit''')
while(True):
    cc = len(os.listdir(path1))
    ncc = len(os.listdir(path2))
    ret,frame = cap.read()
    if not ret:
        break
    cv2.imshow("Data Collection", frame)
    key = cv2.waitKey(1)
    if(key == ord('s')):
        filename = f"{path1}/{cc}.jpg"
        cv2.imwrite(filename,frame)
        print("Crack Wall sample is saved")
    elif(key == ord('a')):
        filename = f"{path2}/{ncc}.jpg"
        cv2.imwrite(filename,frame)
        print("No-Crack Wall sample is saved")
    elif(key == ord('q')):
        print("Sample Collection Process is coompleted")
        break
cap.release()
cv2.destroyAllWindows()
    





    
