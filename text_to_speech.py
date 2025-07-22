import queue
import threading
import time
import tempfile
import os
import subprocess
import logging
from gtts import gTTS
import pygame
from config import logger

class TextToSpeech:
    def __init__(self):
        self.message_queue = queue.Queue()
        self.speaking = False
        self.stop_speaking = False
        self.speech_thread = None
        self.audio_initialized = False
        
        # Initialize audio system
        self.init_audio()
        
        # Start the speech processing thread
        self.speech_thread = threading.Thread(target=self._process_speech_queue, daemon=True)
        self.speech_thread.start()

    def init_audio(self):
        """Initialize audio system with multiple fallback options for Raspberry Pi"""
        try:
            # First, try to initialize pygame mixer with specific settings for Raspberry Pi
            pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=4096)
            pygame.mixer.init()
            
            # Test if audio is working
            if pygame.mixer.get_init() is not None:
                logger.info("Pygame mixer initialized successfully")
                self.audio_initialized = True
                return
        except Exception as e:
            logger.warning(f"Pygame mixer initialization failed: {e}")

        # Try alternative audio backends
        backends = ['alsa', 'pulse', 'oss']
        for backend in backends:
            try:
                os.environ['SDL_AUDIODRIVER'] = backend
                pygame.mixer.quit()  # Clean up previous attempt
                pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=4096)
                pygame.mixer.init()
                
                if pygame.mixer.get_init() is not None:
                    logger.info(f"Audio initialized with {backend} backend")
                    self.audio_initialized = True
                    return
            except Exception as e:
                logger.warning(f"Failed to initialize audio with {backend}: {e}")

        logger.error("Could not initialize any audio backend")
        self.audio_initialized = False

    def _process_speech_queue(self):
        """Process TTS messages in a background thread."""
        while not self.stop_speaking:
            try:
                # Wait for a message with timeout
                message = self.message_queue.get(timeout=1)
                if message and not self.stop_speaking:
                    self.speaking = True
                    try:
                        self._speak_message(message)
                    except Exception as e:
                        logger.error(f"Error speaking message '{message}': {e}")
                    finally:
                        self.speaking = False
                        
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Speech queue processing error: {e}")
                self.speaking = False
                time.sleep(1)

    def _speak_message(self, message):
        """Generate and play TTS audio"""
        if not message or self.stop_speaking:
            return

        try:
            # Try pygame method first if audio is initialized
            if self.audio_initialized and not self.stop_speaking:
                if self._speak_with_pygame(message):
                    return

            # Fallback to system audio commands
            logger.info("Falling back to system audio commands")
            self._speak_with_system_command(message)
            
        except Exception as e:
            logger.error(f"All TTS methods failed for message '{message}': {e}")

    def _speak_with_pygame(self, message):
        """Generate speech using gTTS and play it with pygame."""
        try:
            # Create a temporary MP3 file
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmpfile:
                temp_filename = tmpfile.name
                
            try:
                # Generate TTS audio
                logger.debug(f"Generating TTS for: {message}")
                tts = gTTS(text=message, lang='en', slow=False)
                tts.save(temp_filename)
                
                # Load and play the audio
                pygame.mixer.music.load(temp_filename)
                pygame.mixer.music.play()
                
                # Wait for speech to finish (or stop if requested)
                while pygame.mixer.music.get_busy() and not self.stop_speaking:
                    time.sleep(0.1)
                
                # Stop music if still playing
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()
                    
                logger.debug(f"Successfully played TTS: {message}")
                return True
                
            finally:
                # Clean up temporary file
                try:
                    if os.path.exists(temp_filename):
                        os.unlink(temp_filename)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temp file: {cleanup_error}")
                    
        except Exception as e:
            logger.error(f"Pygame TTS error: {e}")
            return False

    def _speak_with_system_command(self, message):
        """Fallback TTS using system commands (espeak, festival, etc.)"""
        try:
            # Try espeak first (most common on Raspberry Pi)
            if self._try_espeak(message):
                return
                
            # Try festival as backup
            if self._try_festival(message):
                return
                
            # Try aplay with gTTS generated file
            if self._try_aplay_with_gtts(message):
                return
                
            logger.warning(f"All system TTS methods failed for: {message}")
            
        except Exception as e:
            logger.error(f"System command TTS error: {e}")

    def _try_espeak(self, message):
        """Try using espeak for TTS"""
        try:
            # Check if espeak is available
            result = subprocess.run(['which', 'espeak'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            if result.returncode != 0:
                return False
                
            # Use espeak to speak
            subprocess.run(['espeak', '-s', '150', '-v', 'en', message], 
                          timeout=30, 
                          check=True)
            logger.info(f"Successfully used espeak for: {message}")
            return True
            
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.debug(f"espeak failed: {e}")
            return False

    def _try_festival(self, message):
        """Try using festival for TTS"""
        try:
            # Check if festival is available
            result = subprocess.run(['which', 'festival'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            if result.returncode != 0:
                return False
                
            # Use festival to speak
            process = subprocess.Popen(['festival', '--tts'], 
                                     stdin=subprocess.PIPE, 
                                     text=True,
                                     timeout=30)
            process.communicate(input=message)
            
            if process.returncode == 0:
                logger.info(f"Successfully used festival for: {message}")
                return True
                
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.debug(f"festival failed: {e}")
            return False

    def _try_aplay_with_gtts(self, message):
        """Try using aplay with gTTS generated WAV file"""
        try:
            # Check if aplay is available
            result = subprocess.run(['which', 'aplay'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            if result.returncode != 0:
                return False

            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmpfile:
                wav_filename = tmpfile.name
                
            try:
                # Generate TTS audio and convert to WAV
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as mp3_tmpfile:
                    mp3_filename = mp3_tmpfile.name
                
                # Generate MP3 with gTTS
                tts = gTTS(text=message, lang='en', slow=False)
                tts.save(mp3_filename)
                
                # Convert MP3 to WAV using ffmpeg or sox
                if self._convert_mp3_to_wav(mp3_filename, wav_filename):
                    # Play WAV with aplay
                    subprocess.run(['aplay', wav_filename], 
                                 timeout=30, 
                                 check=True,
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                    logger.info(f"Successfully used aplay for: {message}")
                    return True
                    
            finally:
                # Cleanup temp files
                for filename in [wav_filename, mp3_filename]:
                    try:
                        if os.path.exists(filename):
                            os.unlink(filename)
                    except Exception:
                        pass
                        
        except Exception as e:
            logger.debug(f"aplay with gTTS failed: {e}")
            return False

    def _convert_mp3_to_wav(self, mp3_file, wav_file):
        """Convert MP3 to WAV using available tools"""
        converters = [
            ['ffmpeg', '-i', mp3_file, '-acodec', 'pcm_s16le', '-ar', '22050', wav_file],
            ['sox', mp3_file, wav_file],
            ['mpg123', '-w', wav_file, mp3_file]
        ]
        
        for converter in converters:
            try:
                subprocess.run(converter, 
                             timeout=15, 
                             check=True,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
                return True
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                continue
                
        return False

    def speak(self, message):
        """Add a message to the TTS queue."""
        if not message:
            return
            
        # Print message for debugging
        print(f"TTS: {message}")
        logger.info(f"TTS queued: {message}")
        
        try:
            # Clear any old messages if queue is getting full
            if self.message_queue.qsize() > 5:
                try:
                    while not self.message_queue.empty():
                        self.message_queue.get_nowait()
                except queue.Empty:
                    pass
                logger.warning("TTS queue was full, cleared old messages")
            
            # Add new message
            self.message_queue.put(message, timeout=1)
            
        except queue.Full:
            logger.warning(f"TTS queue full, dropping message: {message}")
        except Exception as e:
            logger.error(f"Error adding message to TTS queue: {e}")

    def is_speaking(self):
        """Check if currently speaking"""
        return self.speaking

    def stop(self):
        """Stop TTS playback and clean up."""
        logger.info("Stopping TTS system")
        self.stop_speaking = True
        
        # Stop pygame audio
        if self.audio_initialized:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
            except Exception as e:
                logger.warning(f"Error stopping pygame audio: {e}")
        
        # Wait for speech thread to finish
        if self.speech_thread and self.speech_thread.is_alive():
            self.speech_thread.join(timeout=2)
            
        logger.info("TTS system stopped")

    def wait_until_done(self, timeout=30):
        """Wait until all queued messages are spoken"""
        start_time = time.time()
        while (not self.message_queue.empty() or self.speaking) and not self.stop_speaking:
            if time.time() - start_time > timeout:
                logger.warning("TTS wait timeout reached")
                break
            time.sleep(0.1)
    
    # Add these improvements to your existing TextToSpeech class

    def init_audio(self):
        """Initialize audio system with multiple fallback options for Raspberry Pi"""
        # Check if running in headless mode or if audio hardware exists
        if not self._check_audio_hardware():
            logger.warning("No audio hardware detected, will use system commands only")
            self.audio_initialized = False
            return
        
        try:
            # First, try to initialize pygame mixer with specific settings for Raspberry Pi
            pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=4096)
            pygame.mixer.init()
            
            # Test if audio is working
            if pygame.mixer.get_init() is not None:
                logger.info("Pygame mixer initialized successfully")
                self.audio_initialized = True
                return
        except Exception as e:
            logger.warning(f"Pygame mixer initialization failed: {e}")

        # Try alternative audio backends
        backends = ['alsa', 'pulse', 'oss']
        for backend in backends:
            try:
                os.environ['SDL_AUDIODRIVER'] = backend
                pygame.mixer.quit()  # Clean up previous attempt
                pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=4096)
                pygame.mixer.init()
                
                if pygame.mixer.get_init() is not None:
                    logger.info(f"Audio initialized with {backend} backend")
                    self.audio_initialized = True
                    return
            except Exception as e:
                logger.warning(f"Failed to initialize audio with {backend}: {e}")

        logger.error("Could not initialize any audio backend")
        self.audio_initialized = False

    def _check_audio_hardware(self):
        """Check if audio hardware is available"""
        try:
            # Check ALSA cards
            with open('/proc/asound/cards', 'r') as f:
                cards = f.read().strip()
                if cards and not cards.startswith('---'):
                    return True
        except FileNotFoundError:
            pass
        
        try:
            # Check for audio devices
            result = subprocess.run(['aplay', '-l'], 
                                capture_output=True, 
                                text=True, 
                                timeout=5)
            return result.returncode == 0 and 'card' in result.stdout.lower()
        except Exception:
            pass
        
        return False

    def _try_espeak(self, message):
        """Try using espeak for TTS"""
        try:
            # Check if espeak is available
            result = subprocess.run(['which', 'espeak'], 
                                capture_output=True, 
                                text=True, 
                                timeout=5)
            if result.returncode != 0:
                return False
            
            # Use espeak with better parameters for Raspberry Pi
            cmd = [
                'espeak', 
                '-s', '150',        # Speed
                '-v', 'en+f3',      # Voice (female, variant 3)
                '-a', '100',        # Amplitude
                '-p', '50',         # Pitch
                message
            ]
            
            subprocess.run(cmd, 
                        timeout=30, 
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE)
            logger.info(f"Successfully used espeak for: {message}")
            return True
            
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.debug(f"espeak failed: {e}")
            return False

    def _try_pico2wave(self, message):
        """Try using pico2wave (SVOX TTS) - often pre-installed on RPi"""
        try:
            # Check if pico2wave is available
            result = subprocess.run(['which', 'pico2wave'], 
                                capture_output=True, 
                                text=True, 
                                timeout=5)
            if result.returncode != 0:
                return False

            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmpfile:
                wav_filename = tmpfile.name
                
            try:
                # Generate speech with pico2wave
                subprocess.run(['pico2wave', '-l', 'en-US', '-w', wav_filename, message], 
                            timeout=15, 
                            check=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
                
                # Play with aplay
                subprocess.run(['aplay', wav_filename], 
                            timeout=30, 
                            check=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
                
                logger.info(f"Successfully used pico2wave for: {message}")
                return True
                
            finally:
                try:
                    if os.path.exists(wav_filename):
                        os.unlink(wav_filename)
                except Exception:
                    pass
                    
        except Exception as e:
            logger.debug(f"pico2wave failed: {e}")
            return False

    def _speak_with_system_command(self, message):
        """Fallback TTS using system commands (espeak, festival, etc.)"""
        try:
            # Try espeak first (most common on Raspberry Pi)
            if self._try_espeak(message):
                return
                
            # Try pico2wave (often pre-installed)
            if self._try_pico2wave(message):
                return
            
            # Try festival as backup
            if self._try_festival(message):
                return
                
            # Try aplay with gTTS generated file
            if self._try_aplay_with_gtts(message):
                return
                
            logger.warning(f"All system TTS methods failed for: {message}")
            
        except Exception as e:
            logger.error(f"System command TTS error: {e}")

    # Add this method to check TTS availability on startup
    def test_tts_capabilities(self):
        """Test what TTS methods are available"""
        available_methods = []
        
        # Test pygame
        if self.audio_initialized:
            available_methods.append("pygame")
        
        # Test system commands
        commands_to_test = [
            ('espeak', ['espeak', '--version']),
            ('pico2wave', ['pico2wave', '-l']),
            ('festival', ['festival', '--version']),
            ('aplay', ['aplay', '--version'])
        ]
        
        for name, cmd in commands_to_test:
            try:
                result = subprocess.run(cmd, 
                                    capture_output=True, 
                                    timeout=5)
                if result.returncode == 0:
                    available_methods.append(name)
            except Exception:
                pass
        
        logger.info(f"Available TTS methods: {', '.join(available_methods) if available_methods else 'None'}")
        return available_methods

# Global TTS instance
tts = TextToSpeech()

def speak(message):
    """Global speak function"""
    tts.speak(message)