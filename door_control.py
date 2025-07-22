# door_control.py
import cv2
import requests
import time
import logging
from threading import Thread, Lock, Event
from PIL import Image
import io
try:
    import RPi.GPIO as GPIO
    from picamera2 import Picamera2
    RASPBERRY_PI = True
    print("Running on Raspberry Pi - GPIO and PiCamera enabled")
except ImportError:
    RASPBERRY_PI = False
    print("Running in non-Raspberry Pi mode (GPIO and PiCamera disabled)")
from config import *
from face_detector import FaceDetector
from livestream import LiveStream
from async_requests import AsyncRequestManager
from text_to_speech import TextToSpeech

logger = logging.getLogger(__name__)
tts = TextToSpeech()

def speak(message):
    """Global speak function"""
    tts.speak(message)

class DoorControlSystem:
    def __init__(self):
        speak("Initializing optimized door control system with HiveMQ MQTT streaming")
        self.camera = None
        self.webcam = None
        self.running = False
        self.stop_event = Event()
        self.camera_type = None
        self.last_capture_time = 0
        self.capture_lock = Lock()
        self.face_detector = FaceDetector(FACE_DETECTION_METHOD) if FACE_DETECTION_ENABLED else None
        self.livestream = None
        if MQTT_STREAMING_ENABLED:
            self.livestream = LiveStream(
                camera_type=None,
                camera=None,
                webcam=None,
                broker_host=MQTT_BROKER_HOST,
                broker_port=MQTT_BROKER_PORT,
                topic=MQTT_TOPIC,
                client_id=MQTT_CLIENT_ID,
                username=MQTT_USERNAME,
                password=MQTT_PASSWORD,
                use_tls=MQTT_USE_TLS,
                ca_certs=MQTT_CA_CERTS,
                width=LIVESTREAM_WIDTH,
                height=LIVESTREAM_HEIGHT,
                fps=LIVESTREAM_FPS
            )
        self.stats = {
            'total_captures': 0,
            'faces_detected': 0,
            'api_calls_made': 0,
            'api_calls_saved': 0,
            'frames_streamed': 0
        }
        self.request_manager = AsyncRequestManager()
        self.processor_thread = Thread(target=self._request_processor)
        self.processor_thread.daemon = True
        self.processor_thread.start()
        if RASPBERRY_PI:
            self.setup_gpio()
            self.setup_pi_camera()
        else:
            self.setup_webcam()
        if self.livestream:
            self.livestream.camera_type = self.camera_type
            self.livestream.camera = self.camera
            self.livestream.webcam = self.webcam
    
    def _request_processor(self):
        while True:
            try:
                self.request_manager.process_completed_requests()
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Request processor error: {e}")
                time.sleep(1)
    
    def setup_gpio(self):
        speak("Setting up GPIO pins")
        if not RASPBERRY_PI:
            return
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(DOOR_RELAY_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(LED_GREEN_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(LED_RED_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        logger.info("GPIO setup completed")
        speak("GPIO setup completed")

    def setup_pi_camera(self):
        speak("Setting up Pi camera")
        try:
            self.camera = Picamera2()
            config = self.camera.create_still_configuration(
                main={"size": (IMAGE_MAX_WIDTH, IMAGE_MAX_HEIGHT)},
                lores={"size": (320, 240)},
                display="lores"
            )
            self.camera.configure(config)
            self.camera.start()
            time.sleep(2)
            self.camera_type = "pi"
            logger.info("Pi Camera initialized successfully")
            speak("Pi camera ready")
        except Exception as e:
            logger.error(f"Failed to initialize Pi Camera: {e}")
            speak("Pi camera failed, using webcam")
            self.setup_webcam()
    
    def setup_webcam(self):
        speak("Setting up web camera")
        try:
            self.webcam = cv2.VideoCapture(WEBCAM_INDEX)
            if not self.webcam.isOpened():
                raise RuntimeError("Could not open webcam")
            self.webcam.set(cv2.CAP_PROP_FRAME_WIDTH, IMAGE_MAX_WIDTH)
            self.webcam.set(cv2.CAP_PROP_FRAME_HEIGHT, IMAGE_MAX_HEIGHT)
            ret, frame = self.webcam.read()
            if not ret:
                raise RuntimeError("Could not read from webcam")
            self.camera_type = "webcam"
            logger.info(f"Webcam initialized successfully")
            speak("Web camera ready")
        except Exception as e:
            logger.error(f"Failed to initialize webcam: {e}")
            speak("Web camera failed")
            raise
    
    def capture_image(self):
        with self.capture_lock:
            current_time = time.time()
            if current_time - self.last_capture_time < CAPTURE_COOLDOWN:
                logger.debug("Capture skipped - cooldown period")
                return None
            try:
                if self.camera_type == "pi" and self.camera:
                    buffer = io.BytesIO()
                    self.camera.capture_file(buffer, format='jpeg')
                    buffer.seek(0)
                    image_data = buffer.getvalue()
                elif self.camera_type == "webcam" and self.webcam:
                    ret, frame = self.webcam.read()
                    if not ret:
                        raise RuntimeError("Failed to capture from webcam")
                    height, width = frame.shape[:2]
                    if width > IMAGE_MAX_WIDTH or height > IMAGE_MAX_HEIGHT:
                        scale_w = IMAGE_MAX_WIDTH / width
                        scale_h = IMAGE_MAX_HEIGHT / height
                        scale = min(scale_w, scale_h)
                        new_width = int(width * scale)
                        new_height = int(height * scale)
                        frame = cv2.resize(frame, (new_width, new_height))
                    encode_params = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
                    ret, buffer = cv2.imencode('.jpg', frame, encode_params)
                    if not ret:
                        raise RuntimeError("Failed to encode image")
                    image_data = buffer.tobytes()
                else:
                    raise RuntimeError("No camera available")
                image = Image.open(io.BytesIO(image_data))
                if image.width > IMAGE_MAX_WIDTH or image.height > IMAGE_MAX_HEIGHT:
                    image.thumbnail((IMAGE_MAX_WIDTH, IMAGE_MAX_HEIGHT), Image.Resampling.LANCZOS)
                output_buffer = io.BytesIO()
                image.save(output_buffer, format='JPEG', quality=JPEG_QUALITY, optimize=True)
                optimized_data = output_buffer.getvalue()
                self.last_capture_time = time.time()
                self.stats['total_captures'] += 1
                if self.livestream and self.livestream.running:
                    if self.livestream.send_frame(optimized_data):
                        self.stats['frames_streamed'] += 1
                        logger.debug("Frame sent to MQTT topic from capture")
                logger.debug(f"Image captured: {len(optimized_data)} bytes")
                return optimized_data
            except Exception as e:
                logger.error(f"Failed to capture image: {e}")
                return None
    
    def verification_callback(self, result, error):
        if error:
            logger.error(f"Verification error: {error}")
            self.indicate_access_denied(f"System error: {error}")
            return
        if not result:
            logger.warning("Verification failed - no result")
            self.indicate_access_denied("Verification failed")
            return
        try:
            open_door = result.get('openDoor', False)
            access_status = result.get('access', 'denied')
            user_name = result.get('user', 'Unknown')
            reason = result.get('reason', 'Unknown error')
            confidence = result.get('confidence', 0)
            if open_door and access_status == 'granted':
                logger.info(f"ACCESS GRANTED - User: {user_name}, Confidence: {confidence}")
                Thread(target=self.control_door, args=(True,)).start()
                Thread(target=self.indicate_access_granted, args=(user_name,)).start()
            else:
                logger.warning(f"ACCESS DENIED - Reason: {reason}")
                Thread(target=self.indicate_access_denied, args=(reason,)).start()
        except Exception as e:
            logger.error(f"Error processing verification result: {e}")
            Thread(target=self.indicate_access_denied, args=("System error",)).start()
    
    def control_door(self, open_door=False):
        if not RASPBERRY_PI:
            logger.info(f"Simulating door {'open' if open_door else 'close'}")
            return
        try:
            if open_door:
                logger.info("Opening door")
                GPIO.output(DOOR_RELAY_PIN, GPIO.HIGH)
                time.sleep(DOOR_OPEN_DURATION)
                GPIO.output(DOOR_RELAY_PIN, GPIO.LOW)
                logger.info("Door closed")
            else:
                GPIO.output(DOOR_RELAY_PIN, GPIO.LOW)
        except Exception as e:
            logger.error(f"Error controlling door: {e}")
    
    def indicate_access_granted(self, user_name):
        speak(f"Access granted. Welcome {user_name}")
        if not RASPBERRY_PI:
            logger.info(f"Access granted for {user_name} (simulated)")
            return
        try:
            GPIO.output(LED_GREEN_PIN, GPIO.HIGH)
            GPIO.output(LED_RED_PIN, GPIO.LOW)
            for _ in range(2):
                GPIO.output(BUZZER_PIN, GPIO.HIGH)
                time.sleep(0.1)
                GPIO.output(BUZZER_PIN, GPIO.LOW)
                time.sleep(0.1)
            time.sleep(DOOR_OPEN_DURATION)
            GPIO.output(LED_GREEN_PIN, GPIO.LOW)
        except Exception as e:
            logger.error(f"Error in access granted indication: {e}")
    
    def indicate_access_denied(self, reason):
        speak(f"Access denied. {reason}")
        if not RASPBERRY_PI:
            logger.info(f"Access denied: {reason} (simulated)")
            return
        try:
            GPIO.output(LED_RED_PIN, GPIO.HIGH)
            GPIO.output(LED_GREEN_PIN, GPIO.LOW)
            for _ in range(3):
                GPIO.output(BUZZER_PIN, GPIO.HIGH)
                time.sleep(0.3)
                GPIO.output(BUZZER_PIN, GPIO.LOW)
                time.sleep(0.2)
            time.sleep(2)
            GPIO.output(LED_RED_PIN, GPIO.LOW)
        except Exception as e:
            logger.error(f"Error in access denied indication: {e}")
    
    def capture_and_verify_async(self):
        try:
            image_data = self.capture_image()
            if not image_data:
                logger.debug("Capture failed or skipped")
                return
            if FACE_DETECTION_ENABLED and self.face_detector:
                start_time = time.time()
                has_face = self.face_detector.has_face(image_data)
                detection_time = time.time() - start_time
                logger.debug(f"Face detection completed in {detection_time:.3f}s")
                if has_face:
                    self.stats['faces_detected'] += 1
                    logger.info("Face detected - proceeding with verification")
                    request_id = self.request_manager.submit_request(
                        image_data, 
                        self.verification_callback
                    )
                    if request_id:
                        self.stats['api_calls_made'] += 1
                        logger.debug(f"Verification request {request_id} submitted")
                        status = self.request_manager.get_status()
                        logger.info(f"System status: {status['active_requests']} active, "
                                   f"{status['pending_requests']} pending requests")
                    else:
                        logger.warning("Failed to submit verification request")
                else:
                    self.stats['api_calls_saved'] += 1
                    logger.debug("No face detected - skipping API call")
            else:
                logger.debug("Face detection disabled - proceeding with verification")
                request_id = self.request_manager.submit_request(
                    image_data, 
                    self.verification_callback
                )
                if request_id:
                    self.stats['api_calls_made'] += 1
                    logger.debug(f"Verification request {request_id} submitted")
                else:
                    logger.warning("Failed to submit verification request")
        except Exception as e:
            logger.error(f"Error in async capture and verify: {e}")
    
    def print_statistics(self):
        if self.stats['total_captures'] > 0:
            efficiency = (self.stats['api_calls_saved'] / self.stats['total_captures']) * 100
            logger.info(f"System Statistics:")
            logger.info(f"  Total captures: {self.stats['total_captures']}")
            logger.info(f"  Faces detected: {self.stats['faces_detected']}")
            logger.info(f"  API calls made: {self.stats['api_calls_made']}")
            logger.info(f"  API calls saved: {self.stats['api_calls_saved']}")
            logger.info(f"  Efficiency: {efficiency:.1f}% calls saved")
            logger.info(f"  Frames streamed: {self.stats['frames_streamed']}")
    
    def manual_capture_handler(self):
        if not RASPBERRY_PI:
            return
        while self.running:
            try:
                if GPIO.input(BUTTON_PIN) == GPIO.LOW:
                    logger.info("Manual capture triggered")
                    self.capture_and_verify_async()
                    time.sleep(1)
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in manual capture handler: {e}")
    
    def run_automatic_mode(self):
        speak("Automatic mode activated with face detection")
        logger.info("Starting automatic capture mode with face detection")
        stats_print_interval = 60
        last_stats_time = time.time()
        while self.running:
            try:
                if not self.stop_event.wait(CAPTURE_INTERVAL):
                    self.capture_and_verify_async()
                    current_time = time.time()
                    if current_time - last_stats_time >= stats_print_interval:
                        self.print_statistics()
                        last_stats_time = current_time
                else:
                    break
            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                break
            except Exception as e:
                logger.error(f"Error in automatic mode: {e}")
                time.sleep(5)
    
    def start(self, manual_mode=False):
        speak("Starting optimized door control system with HiveMQ MQTT streaming")
        try:
            self.running = True
            logger.info("Optimized door control system starting...")
            if FACE_DETECTION_ENABLED:
                logger.info(f"Face detection enabled using {FACE_DETECTION_METHOD} method")
                speak(f"Face detection enabled using {FACE_DETECTION_METHOD}")
            else:
                logger.info("Face detection disabled")
                speak("Face detection disabled")
            if self.livestream and MQTT_STREAMING_ENABLED:
                self.livestream.start()
            try:
                health_response = requests.get(f"{API_BASE_URL}/health", timeout=3)
                if health_response.status_code == 200:
                    logger.info("API connectivity confirmed")
                    speak("Server connected")
                else:
                    logger.warning("API may not be responding correctly")
                    speak("Server warning")
            except:
                logger.warning("Could not connect to API - will retry during operation")
                speak("Server connection failed, will retry")
            if manual_mode and RASPBERRY_PI:
                manual_thread = Thread(target=self.manual_capture_handler)
                manual_thread.daemon = True
                manual_thread.start()
                logger.info("Manual mode active - press button to capture")
                speak("Manual mode ready")
                while self.running:
                    time.sleep(1)
            else:
                if manual_mode and not RASPBERRY_PI:
                    logger.info("Manual mode not available in non-RPi mode")
                    speak("Manual mode not available")
                self.run_automatic_mode()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            speak("System interrupted")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            speak("System error")
        finally:
            self.stop()
    
    def stop(self):
        speak("System shutting down")
        logger.info("Stopping optimized door control system...")
        self.print_statistics()
        self.running = False
        self.stop_event.set()
        if self.livestream:
            self.livestream.stop()
        if RASPBERRY_PI:
            GPIO.output(LED_GREEN_PIN, GPIO.LOW)
            GPIO.output(LED_RED_PIN, GPIO.LOW)
            GPIO.output(BUZZER_PIN, GPIO.LOW)
            GPIO.output(DOOR_RELAY_PIN, GPIO.LOW)
        if self.camera_type == "pi" and self.camera:
            self.camera.stop()
            self.camera.close()
        elif self.camera_type == "webcam" and self.webcam:
            self.webcam.release()
        if RASPBERRY_PI:
            GPIO.cleanup()
        self.request_manager.executor.shutdown(wait=False)
        logger.info("System stopped")