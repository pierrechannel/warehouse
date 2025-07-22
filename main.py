#!/usr/bin/env python3
# main.py
import logging
import argparse
from door_control import DoorControlSystem, speak
from config import *

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

def main():
    speak("Starting optimized door control application with HiveMQ MQTT streaming")
    global API_BASE_URL, VERIFY_ENDPOINT, WEBCAM_INDEX, RESPONSE_TIMEOUT
    global IMAGE_MAX_WIDTH, IMAGE_MAX_HEIGHT, JPEG_QUALITY, MAX_CONCURRENT_REQUESTS
    global FACE_DETECTION_ENABLED, FACE_DETECTION_METHOD, MIN_FACE_SIZE, MAX_FACE_SIZE
    global MQTT_STREAMING_ENABLED, MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_TOPIC
    global MQTT_USERNAME, MQTT_PASSWORD, MQTT_USE_TLS, MQTT_CA_CERTS
    global LIVESTREAM_FPS, LIVESTREAM_WIDTH, LIVESTREAM_HEIGHT
    
    parser = argparse.ArgumentParser(description='Optimized Door Control System with Face Detection and HiveMQ MQTT Streaming')
    parser.add_argument('--manual', action='store_true', 
                       help='Run in manual mode (button triggered)')
    parser.add_argument('--api-url', default=API_BASE_URL,
                       help='Face verification API base URL')
    parser.add_argument('--webcam-index', type=int, default=WEBCAM_INDEX,
                       help='Webcam index (default: 0)')
    parser.add_argument('--timeout', type=int, default=RESPONSE_TIMEOUT,
                       help='API response timeout in seconds (default: 45)')
    parser.add_argument('--max-concurrent', type=int, default=MAX_CONCURRENT_REQUESTS,
                       help='Maximum concurrent API requests (default: 3)')
    parser.add_argument('--image-width', type=int, default=IMAGE_MAX_WIDTH,
                       help='Maximum image width (default: 640)')
    parser.add_argument('--image-height', type=int, default=IMAGE_MAX_HEIGHT,
                       help='Maximum image height (default: 480)')
    parser.add_argument('--jpeg-quality', type=int, default=JPEG_QUALITY,
                       help='JPEG compression quality 0-100 (default: 75)')
    parser.add_argument('--no-face-detection', action='store_true',
                       help='Disable face detection (process all captures)')
    parser.add_argument('--face-method', choices=['haar', 'dnn', 'hog'], 
                       default=FACE_DETECTION_METHOD,
                       help='Face detection method (default: haar)')
    parser.add_argument('--min-face-size', type=int, nargs=2, 
                       default=MIN_FACE_SIZE, metavar=('WIDTH', 'HEIGHT'),
                       help='Minimum face size in pixels (default: 50 50)')
    parser.add_argument('--max-face-size', type=int, nargs=2, 
                       default=MAX_FACE_SIZE, metavar=('WIDTH', 'HEIGHT'),
                       help='Maximum face size in pixels (default: 400 400)')
    parser.add_argument('--mqtt-stream', action='store_true',
                       help='Enable MQTT streaming')
    parser.add_argument('--mqtt-broker-host', default=MQTT_BROKER_HOST,
                       help='HiveMQ broker host (e.g., <your-cluster>.s2.eu.hivemq.cloud)')
    parser.add_argument('--mqtt-broker-port', type=int, default=MQTT_BROKER_PORT,
                       help='HiveMQ broker port (default: 8883 for TLS)')
    parser.add_argument('--mqtt-topic', default=MQTT_TOPIC,
                       help='MQTT topic for streaming (default: door/stream)')
    parser.add_argument('--mqtt-username', default=MQTT_USERNAME,
                       help='HiveMQ broker username')
    parser.add_argument('--mqtt-password', default=MQTT_PASSWORD,
                       help='HiveMQ broker password')
    parser.add_argument('--mqtt-use-tls', action='store_true', default=MQTT_USE_TLS,
                       help='Enable TLS for MQTT connection (default: True)')
    parser.add_argument('--mqtt-ca-certs', default=MQTT_CA_CERTS,
                       help='Path to CA certificate file for TLS')
    parser.add_argument('--mqtt-fps', type=int, default=2,
                       help='Streaming frames per second (default: 2)')
    parser.add_argument('--mqtt-width', type=int, default=LIVESTREAM_WIDTH,
                       help='Streaming frame width (default: 640)')
    parser.add_argument('--mqtt-height', type=int, default=LIVESTREAM_HEIGHT,
                       help='Streaming frame height (default: 480)')
    
    args = parser.parse_args()
    
    API_BASE_URL = args.api_url
    VERIFY_ENDPOINT = f"{API_BASE_URL}/verify"
    WEBCAM_INDEX = args.webcam_index
    RESPONSE_TIMEOUT = args.timeout
    IMAGE_MAX_WIDTH = args.image_width
    IMAGE_MAX_HEIGHT = args.image_height
    JPEG_QUALITY = args.jpeg_quality
    MAX_CONCURRENT_REQUESTS = args.max_concurrent
    FACE_DETECTION_ENABLED = not args.no_face_detection
    FACE_DETECTION_METHOD = args.face_method
    MIN_FACE_SIZE = tuple(args.min_face_size)
    MAX_FACE_SIZE = tuple(args.max_face_size)
    MQTT_STREAMING_ENABLED = args.mqtt_stream
    MQTT_BROKER_HOST = args.mqtt_broker_host
    MQTT_BROKER_PORT = args.mqtt_broker_port
    MQTT_TOPIC = args.mqtt_topic
    MQTT_USERNAME = args.mqtt_username
    MQTT_PASSWORD = args.mqtt_password
    MQTT_USE_TLS = args.mqtt_use_tls
    MQTT_CA_CERTS = args.mqtt_ca_certs
    LIVESTREAM_FPS = args.mqtt_fps
    LIVESTREAM_WIDTH = args.mqtt_width
    LIVESTREAM_HEIGHT = args.mqtt_height
    
    logger.info(f"Configuration: API={API_BASE_URL}, Timeout={RESPONSE_TIMEOUT}s, "
                f"Concurrent={MAX_CONCURRENT_REQUESTS}, Image={IMAGE_MAX_WIDTH}x{IMAGE_MAX_HEIGHT}")
    logger.info(f"Face Detection: {'Enabled' if FACE_DETECTION_ENABLED else 'Disabled'}, "
                f"Method={FACE_DETECTION_METHOD}, "
                f"Size={MIN_FACE_SIZE}-{MAX_FACE_SIZE}")
    logger.info(f"HiveMQ MQTT Streaming: {'Enabled' if MQTT_STREAMING_ENABLED else 'Disabled'}, "
                f"Broker={MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}, Topic={MQTT_TOPIC}, "
                f"TLS={'Enabled' if MQTT_USE_TLS else 'Disabled'}, "
                f"FPS={LIVESTREAM_FPS}, Resolution={LIVESTREAM_WIDTH}x{LIVESTREAM_HEIGHT}")
    
    door_system = DoorControlSystem()
    try:
        door_system.start(manual_mode=args.manual)
    except KeyboardInterrupt:
        logger.info("Program interrupted by user")
        speak("Application interrupted")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        speak("Application error")
    finally:
        door_system.stop()

if __name__ == "__main__":
    print("Initializing Async Door Control System with Face Detection and HiveMQ MQTT Streaming...")
    main()