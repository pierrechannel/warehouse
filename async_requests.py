# request_manager.py
import requests
import uuid
import logging
from threading import Thread, Lock
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from config import *
import time

logger = logging.getLogger(__name__)

class AsyncRequestManager:
    def __init__(self, max_concurrent=MAX_CONCURRENT_REQUESTS):
        self.max_concurrent = max_concurrent
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)
        self.pending_requests = deque()
        self.active_requests = {}
        self.lock = Lock()
        self.request_counter = 0
        
    def submit_request(self, image_data, callback):
        with self.lock:
            self.request_counter += 1
            request_id = f"req_{self.request_counter}_{uuid.uuid4().hex[:8]}"
            if len(self.active_requests) < self.max_concurrent:
                future = self.executor.submit(self._make_request, image_data, request_id)
                self.active_requests[request_id] = {
                    'future': future,
                    'callback': callback,
                    'start_time': time.time()
                }
                logger.info(f"Request {request_id} submitted immediately")
                return request_id
            elif len(self.pending_requests) < PENDING_REQUESTS_LIMIT:
                self.pending_requests.append({
                    'id': request_id,
                    'image_data': image_data,
                    'callback': callback,
                    'queued_time': time.time()
                })
                logger.info(f"Request {request_id} queued (position: {len(self.pending_requests)})")
                return request_id
            else:
                logger.warning(f"Request rejected - queue full ({len(self.pending_requests)} pending)")
                callback(None, "Queue full - system overloaded")
                return None
    
    def _make_request(self, image_data, request_id):
        try:
            files = {'image': ('capture.jpg', image_data, 'image/jpeg')}
            start_time = time.time()
            logger.info(f"Request {request_id} starting API call")
            response = requests.post(
                VERIFY_ENDPOINT,
                files=files,
                timeout=RESPONSE_TIMEOUT
            )
            end_time = time.time()
            request_time = end_time - start_time
            logger.info(f"Request {request_id} completed in {request_time:.2f}s")
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Request {request_id} failed with status {response.status_code}")
                return None
        except requests.exceptions.Timeout:
            logger.error(f"Request {request_id} timed out after {RESPONSE_TIMEOUT}s")
            return None
        except Exception as e:
            logger.error(f"Request {request_id} failed: {e}")
            return None
    
    def process_completed_requests(self):
        with self.lock:
            completed_requests = []
            for request_id, request_info in self.active_requests.items():
                if request_info['future'].done():
                    completed_requests.append(request_id)
            for request_id in completed_requests:
                request_info = self.active_requests.pop(request_id)
                try:
                    result = request_info['future'].result()
                    total_time = time.time() - request_info['start_time']
                    logger.info(f"Request {request_id} processed in {total_time:.2f}s total")
                    if request_info['callback']:
                        Thread(target=request_info['callback'], args=(result, None)).start()
                except Exception as e:
                    logger.error(f"Request {request_id} callback error: {e}")
                    if request_info['callback']:
                        Thread(target=request_info['callback'], args=(None, str(e))).start()
            while (len(self.active_requests) < self.max_concurrent and 
                   len(self.pending_requests) > 0):
                queued_request = self.pending_requests.popleft()
                request_id = queued_request['id']
                future = self.executor.submit(
                    self._make_request, 
                    queued_request['image_data'], 
                    request_id
                )
                self.active_requests[request_id] = {
                    'future': future,
                    'callback': queued_request['callback'],
                    'start_time': time.time()
                }
                queue_time = time.time() - queued_request['queued_time']
                logger.info(f"Request {request_id} started from queue (waited {queue_time:.2f}s)")
    
    def get_status(self):
        with self.lock:
            return {
                'active_requests': len(self.active_requests),
                'pending_requests': len(self.pending_requests),
                'max_concurrent': self.max_concurrent
            }