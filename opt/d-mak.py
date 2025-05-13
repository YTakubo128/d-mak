import math
import cv2
import mediapipe as mp
import d_mak_execute

# MediaPipeのHandモジュールを初期化
mp_drawing = mp.solutions.drawing_utils
mp_hands = mp.solutions.hands

# 手を検出するための初期化
hands = mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.5)

#except handpose
def clacDistance(p0, p1):
  a1 = p1.x-p0.x
  a2 = p1.y-p0.y

  return math.sqrt(a1*a1+a2*a2)

def calcAngle(p0, p1, p2):
  a1 = p1.x-p0.x
  a2 = p1.y-p0.y
  b1 = p2.x-p1.x
  b2 = p2.y-p1.y

  angle = math.acos( (a1*b1 + a2*b2) / (math.sqrt((a1*a1 + a2*a2)*(b1*b1 + b2*b2))) ) * 180/math.pi
  return angle

def calcFingerAngle(p0, p1, p2, p3, p4):
  result = 0
  result += calcAngle(p0, p1, p2)
  result += calcAngle(p1, p2, p3)
  result += calcAngle(p2, p3, p4)

  return result

def detectFingerPose(hand_landmarks):
    result = 0

    if hand_landmarks is not None:  # 手が検出された場合のみ処理を実行
        for hand_landmarks in hand_landmarks:  # 各手のランドマークリストを処理
          thumbIsOpen = calcFingerAngle(hand_landmarks.landmark[0], hand_landmarks.landmark[1], hand_landmarks.landmark[2], hand_landmarks.landmark[3], hand_landmarks.landmark[4]) < 70
          firstFingerIsOpen = calcFingerAngle(hand_landmarks.landmark[0], hand_landmarks.landmark[5], hand_landmarks.landmark[6], hand_landmarks.landmark[7], hand_landmarks.landmark[8]) < 100
          secondFingerIsOpen = calcFingerAngle(hand_landmarks.landmark[0], hand_landmarks.landmark[9], hand_landmarks.landmark[10], hand_landmarks.landmark[11], hand_landmarks.landmark[12]) < 100
          thirdFingerIsOpen = calcFingerAngle(hand_landmarks.landmark[0], hand_landmarks.landmark[13], hand_landmarks.landmark[14], hand_landmarks.landmark[15], hand_landmarks.landmark[16]) < 100
          fourthFingerIsOpen = calcFingerAngle(hand_landmarks.landmark[0], hand_landmarks.landmark[17], hand_landmarks.landmark[18], hand_landmarks.landmark[19], hand_landmarks.landmark[20]) < 100

          #print(fourthFingerIsOpen)
          if(thumbIsOpen and firstFingerIsOpen and secondFingerIsOpen and thirdFingerIsOpen and fourthFingerIsOpen):
            result = 1
          if(not firstFingerIsOpen and not secondFingerIsOpen and not thirdFingerIsOpen and not fourthFingerIsOpen):
            result = 2
          if(firstFingerIsOpen and not secondFingerIsOpen and not thirdFingerIsOpen and not fourthFingerIsOpen):
            result = 3

    return result


#execute action
def executeFingerAction(pose):
  trigger_Functioned = False
  match pose:
    case 1:
      print("paper")

    case 2:
      print("fist")

    case 3:
      print("one")
      if not trigger_Functioned:
        d_mak_execute.executeOne()
        trigger_Functioned = True
        print(trigger_Functioned)



# カメラを起動
cap = cv2.VideoCapture(0)

while cap.isOpened():
    # カメラからフレームを取得
    ret, frame = cap.read()
    if not ret:
        break

    # フレームをRGBに変換
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # 手を検出
    results = hands.process(frame_rgb)

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            # 手の座標を取得
            for point in hand_landmarks.landmark:
                x = int(point.x * frame.shape[1])
                y = int(point.y * frame.shape[0])
                # 座標を表示
                cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)

    executeFingerAction(detectFingerPose(results.multi_hand_landmarks))

    # フレームを表示
    cv2.imshow('Hand Tracking', frame)

    # 'q'を押して終了
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# カメラを解放
cap.release()
cv2.destroyAllWindows()