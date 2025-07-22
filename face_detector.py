import cv2
import numpy as np
import os
import logging
from config import (
    FACE_DETECTION_METHOD, DNN_MODEL_PATH, DNN_CONFIG_PATH,
    MIN_FACE_SIZE, MAX_FACE_SIZE, FACE_CONFIDENCE_THRESHOLD,
    FACE_DETECTION_SCALE_FACTOR, FACE_DETECTION_MIN_NEIGHBORS,
    logger
)

class FaceDetector:
    def __init__(self, method="haar"):
        self.method = method
        self.detector = None
        self.net = None
        self.setup_detector()
    
    def setup_detector(self):
        try:
            if self.method == "haar":
                self.detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
                if self.detector.empty():
                    raise ValueError("Failed to load Haar cascade")
                logger.info("Haar cascade face detector initialized")
                
            elif self.method == "dnn":
                if os.path.exists(DNN_MODEL_PATH) and os.path.exists(DNN_CONFIG_PATH):
                    self.net = cv2.dnn.readNetFromTensorflow(DNN_MODEL_PATH, DNN_CONFIG_PATH)
                    logger.info("DNN face detector initialized")
                else:
                    logger.warning("DNN model files not found, falling back to Haar cascade")
                    self.method = "haar"
                    self.setup_detector()
                    
            elif self.method == "hog":
                try:
                    import dlib
                    self.detector = dlib.get_frontal_face_detector()
                    logger.info("HOG face detector initialized")
                except ImportError:
                    logger.warning("dlib not available, falling back to Haar cascade")
                    self.method = "haar"
                    self.setup_detector()
                    
        except Exception as e:
            logger.error(f"Face detector initialization failed: {e}")
            self.method = "haar"
            self.detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    def detect_faces(self, image_data):
        try:
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                logger.warning("Failed to decode image for face detection")
                return 0, []
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = []
            if self.method == "haar":
                faces = self.detector.detectMultiScale(
                    gray,
                    scaleFactor=FACE_DETECTION_SCALE_FACTOR,
                    minNeighbors=FACE_DETECTION_MIN_NEIGHBORS,
                    minSize=MIN_FACE_SIZE,
                    maxSize=MAX_FACE_SIZE
                )
            elif self.method == "dnn":
                h, w = img.shape[:2]
                blob = cv2.dnn.blobFromImage(img, 1.0, (300, 300), [104, 117, 123])
                self.net.setInput(blob)
                detections = self.net.forward()
                for i in range(detections.shape[2]):
                    confidence = detections[0, 0, i, 2]
                    if confidence > FACE_CONFIDENCE_THRESHOLD:
                        x1 = int(detections[0, 0, i, 3] * w)
                        y1 = int(detections[0, 0, i, 4] * h)
                        x2 = int(detections[0, 0, i, 5] * w)
                        y2 = int(detections[0, 0, i, 6] * h)
                        face_w = x2 - x1
                        face_h = y2 - y1
                        if (face_w >= MIN_FACE_SIZE[0] and face_h >= MIN_FACE_SIZE[1] and
                            face_w <= MAX_FACE_SIZE[0] and face_h <= MAX_FACE_SIZE[1]):
                            faces.append((x1, y1, face_w, face_h))
            elif self.method == "hog":
                import dlib
                dlib_faces = self.detector(gray)
                for face in dlib_faces:
                    x, y, w, h = face.left(), face.top(), face.width(), face.height()
                    if (w >= MIN_FACE_SIZE[0] and h >= MIN_FACE_SIZE[1] and
                        w <= MAX_FACE_SIZE[0] and h <= MAX_FACE_SIZE[1]):
                        faces.append((x, y, w, h))
            valid_faces = []
            for (x, y, w, h) in faces:
                if (w >= MIN_FACE_SIZE[0] and h >= MIN_FACE_SIZE[1] and
                    w <= MAX_FACE_SIZE[0] and h <= MAX_FACE_SIZE[1]):
                    valid_faces.append((x, y, w, h))
            face_count = len(valid_faces)
            if face_count > 0:
                logger.debug(f"Detected {face_count} face(s) using {self.method} method")
            return face_count, valid_faces
        except Exception as e:
            logger.error(f"Face detection error: {e}")
            return 0, []
    
    def has_face(self, image_data):
        face_count, _ = self.detect_faces(image_data)
        return face_count > 0