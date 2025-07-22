import os
import logging
import uuid

# Configuration
API_BASE_URL = "http://192.168.5.41:3000/api"
VERIFY_ENDPOINT = f"{API_BASE_URL}/verify"

# GPIO Pin Configuration (only used on Raspberry Pi)
DOOR_RELAY_PIN = 18
LED_GREEN_PIN = 24
LED_RED_PIN = 23
BUZZER_PIN = 25
BUTTON_PIN = 22

# System Configuration
DOOR_OPEN_DURATION = 5
CAPTURE_INTERVAL = 2
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30
WEBCAM_INDEX = 0
IMAGE_MAX_WIDTH = 640
IMAGE_MAX_HEIGHT = 480
JPEG_QUALITY = 75

# Face Detection Configuration
FACE_DETECTION_ENABLED = True
MIN_FACE_SIZE = (50, 50)
MAX_FACE_SIZE = (400, 400)
FACE_DETECTION_SCALE_FACTOR = 1.1
FACE_DETECTION_MIN_NEIGHBORS = 5
FACE_CONFIDENCE_THRESHOLD = 0.7

# Async Configuration
MAX_CONCURRENT_REQUESTS = 3
PENDING_REQUESTS_LIMIT = 5
RESPONSE_TIMEOUT = 45
CAPTURE_COOLDOWN = 1.0

# MQTT Streaming Configuration
MQTT_STREAMING_ENABLED = False
MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 8883
MQTT_TOPIC = "door/stream"
MQTT_CLIENT_ID = f"door-stream-{uuid.uuid4().hex[:8]}"
MQTT_USERNAME = None
MQTT_PASSWORD = None
MQTT_USE_TLS = True
MQTT_CA_CERTS = None
LIVESTREAM_FPS = 3
LIVESTREAM_WIDTH = 640
LIVESTREAM_HEIGHT = 480

# Face Detection Method Selection
FACE_DETECTION_METHOD = "haar"
DNN_MODEL_PATH = "opencv_face_detector_uint8.pb"
DNN_CONFIG_PATH = "opencv_face_detector.pbtxt"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('door_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)