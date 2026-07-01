import cv2
import mediapipe as mp
import serial
import time
import math
from serial import SerialException

# --- CONSTANTES GLOBAIS ---
SERIAL_PORT = "/dev/cu.usbserial-1140"
BAUD_RATE = 115200
SERIAL_TIMEOUT = 1

RATE_LIMIT_INTERVAL = 1.0 / 15.0  # Limite de 15Hz (66ms por pacote)
DEADBAND_THRESHOLD = 3            # Filtro de ruído (3 graus)
ALPHA = 0.15                      # Fator EMA. Aumenta para resposta mais rápida, diminui para mais suave

# --- FUNÇÕES ---
def map_value(value, in_min, in_max, out_min, out_max):
    """Interpolador linear com clamping absoluto."""
    value = max(min(value, in_max), in_min)
    return int(out_min + (float(value - in_min) / float(in_max - in_min)) * (out_max - out_min))

def calculate_distance(p1, p2):
    return math.sqrt((p2.x - p1.x)**2 + (p2.y - p1.y)**2)

def init_serial():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=SERIAL_TIMEOUT)
        print(f"[INFO] Hardware conectado: {SERIAL_PORT}.")
        time.sleep(2) # Estabilização do bootloader do Arduino
        return ser
    except SerialException as e:
        print(f"[ERRO CRÍTICO] Falha na porta série: {e}")
        return None

# --- PIPELINE PRINCIPAL ---
def main():
    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils
    hands = mp_hands.Hands(
        max_num_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7
    )

    cap = cv2.VideoCapture(0)
    ser = init_serial()

    # Memória de estado e EMA (Inicializado na posição HOME)
    last_angles = [None, None, None]
    last_send_time = 0
    smoothed_angles = [90.0, 90.0, 90.0]

    try:
        while True:
            success, frame = cap.read()
            if not success: 
                break

            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb_frame)

            if results.multi_hand_landmarks:
                hand_landmarks = results.multi_hand_landmarks[0]
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                # Extração Vetorial
                wrist = hand_landmarks.landmark[mp_hands.HandLandmark.WRIST]
                thumb_tip = hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP]
                index_tip = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]

                # Cinemática Alvo
                target_base = map_value(wrist.x, 0.0, 1.0, 180, 0)
                target_shoulder = map_value(wrist.y, 0.0, 1.0, 90, 140)
                
                dist = calculate_distance(thumb_tip, index_tip)
                target_claw = map_value(dist, 0.02, 0.25, 180, 0)  # Inverti aqui a lógica porque abria a mão e a garra fechava e vice-versa

                # Filtro EMA
                smoothed_angles[0] += ALPHA * (target_base - smoothed_angles[0])
                smoothed_angles[1] += ALPHA * (target_shoulder - smoothed_angles[1])
                smoothed_angles[2] += ALPHA * (target_claw - smoothed_angles[2])

                current_angles = [int(smoothed_angles[0]), int(smoothed_angles[1]), int(smoothed_angles[2])]

                # Deadband e Rate Limiter
                send_data = (last_angles[0] is None) or any(abs(c - l) > DEADBAND_THRESHOLD for c, l in zip(current_angles, last_angles))
                current_time = time.time()
                
                if send_data and (current_time - last_send_time) >= RATE_LIMIT_INTERVAL:
                    payload = f"<{current_angles[0]},{current_angles[1]},90,90,{current_angles[2]}>\n"
                    
                    if ser and ser.is_open:
                        ser.write(payload.encode('utf-8'))
                    
                    # LOG DE TERMINAL INJETADO
                    print(f"[TX] Base: {current_angles[0]:03d} | Ombro: {current_angles[1]:03d} | Garra: {current_angles[2]:03d} || (Raw EMA: {smoothed_angles[0]:.1f}, {smoothed_angles[1]:.1f}, {smoothed_angles[2]:.1f})")
                    
                    last_angles = current_angles
                    last_send_time = current_time

                # Telemetria OSD
                cv2.putText(frame, f"Base: {current_angles[0]}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame, f"Ombro: {current_angles[1]}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame, f"Garra: {current_angles[2]} (D:{dist:.2f})", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            cv2.imshow("Adeept 5-DOF - Telemetria Optica", frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'): 
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        if ser: 
            ser.close()

if __name__ == '__main__':
    main()