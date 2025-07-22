# livestream.py
import cv2
import io
import logging
from threading import Thread, Event
import paho.mqtt.client as mqtt
import ssl
from config import *

logger = logging.getLogger(__name__)

class LiveStream:
    def __init__(self, camera_type, camera, webcam, broker_host, broker_port, topic, client_id, username, password, use_tls, ca_certs, width, height, fps):
        self.camera_type = camera_type
        self.camera = camera
        self.webcam = webcam
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic = topic
        self.client_id = client_id
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.ca_certs = ca_certs
        self.width = width
        self.height = height
        self.fps = fps
        self.running = False
        self.stop_event = Event()
        self.stream_thread = None
        self.mqtt_client = None

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info(f"MQTT client connected to {self.broker_host}:{self.broker_port}")
            tts.speak("MQTT streaming connected")
        else:
            logger.error(f"MQTT connection failed with code {rc}")
            tts.speak(f"MQTT connection failed: {rc}")

    def setup_mqtt_client(self):
        try:
            self.mqtt_client = mqtt.Client(client_id=self.client_id, protocol=mqtt.MQTTv5)
            if self.use_tls:
                self.mqtt_client.tls_set(ca_certs=self.ca_certs, tls_version=ssl.PROTOCOL_TLSv1_2)
                logger.info("TLS enabled for MQTT connection")
            if self.username and self.password:
                self.mqtt_client.username_pw_set(self.username, self.password)
                logger.info(f"MQTT authentication set for user: {self.username}")
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.mqtt_client.loop_start()
            logger.info(f"MQTT client initialized for {self.broker_host}:{self.broker_port}, topic: {self.topic}")
        except Exception as e:
            logger.error(f"Failed to initialize MQTT client: {e}")
            tts.speak("MQTT client setup failed")
            self.mqtt_client = None

    def send_frame(self, frame_data):
        if not self.mqtt_client:
            logger.error("MQTT client not initialized")
            return False
        try:
            result = self.mqtt_client.publish(self.topic, frame_data, qos=0)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                return True
            else:
                logger.warning(f"Failed to publish frame to MQTT topic {self.topic}: {result.rc}")
                return False
        except Exception as e:
            logger.error(f"Error publishing frame to MQTT: {e}")
            return False

    def capture_frames(self):
        frame_interval = 0.5  # 1 seconde / 2 images = 0.5 seconde entre chaque image
        while not self.stop_event.is_set():
            try:
                start_time = time.time()
                
                if self.camera_type == "pi" and self.camera:
                    buffer = io.BytesIO()
                    self.camera.capture_file(buffer, format='jpeg')
                    buffer.seek(0)
                    frame_data = buffer.getvalue()
                elif self.camera_type == "webcam" and self.webcam:
                    ret, frame = self.webcam.read()
                    if not ret:
                        logger.error("Failed to capture frame from webcam")
                        time.sleep(frame_interval)
                        continue
                    height, width = frame.shape[:2]
                    if width > self.width or height > self.height:
                        scale_w = self.width / width
                        scale_h = self.height / height
                        scale = min(scale_w, scale_h)
                        new_width = int(width * scale)
                        new_height = int(height * scale)
                        frame = cv2.resize(frame, (new_width, new_height))
                    encode_params = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
                    ret, buffer = cv2.imencode('.jpg', frame, encode_params)
                    if not ret:
                        logger.error("Failed to encode frame")
                        time.sleep(frame_interval)
                        continue
                    frame_data = buffer.tobytes()
                else:
                    logger.error("No camera available for streaming")
                    time.sleep(1)
                    continue
                    
                if self.send_frame(frame_data):
                    logger.debug("Frame published to MQTT topic")
                else:
                    logger.debug("Failed to publish frame")
                    
                # Calcul du temps à attendre pour maintenir le rythme de 2 images/seconde
                processing_time = time.time() - start_time
                sleep_time = max(0, frame_interval - processing_time)
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Error capturing frame: {e}")
                time.sleep(1)
    def start(self):
        self.setup_mqtt_client()
        if not self.mqtt_client:
            logger.error("Cannot start streaming without MQTT client")
            return
        self.running = True
        self.stream_thread = Thread(target=self.capture_frames)
        self.stream_thread.daemon = True
        self.stream_thread.start()
        logger.info(f"Started MQTT streaming to {self.broker_host}:{self.broker_port}, topic: {self.topic}")
        tts.speak("MQTT streaming started")

    def stop(self):
        self.running = False
        self.stop_event.set()
        if self.stream_thread:
            self.stream_thread.join(timeout=2)
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            logger.info("MQTT client disconnected")
        logger.info("MQTT streaming stopped")
        tts.speak("MQTT streaming stopped")