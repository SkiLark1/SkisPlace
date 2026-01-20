import time
import logging
import os
import signal
import sys

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def signal_handler(sig, frame):
    logger.info("Gracefully shutting down...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    logger.info("Worker service started")
    
    # Placeholder for worker loop
    while True:
        try:
            logger.info("Worker heartbeat - waiting for jobs...")
            time.sleep(10)
        except Exception as e:
            logger.error(f"Error in worker loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
