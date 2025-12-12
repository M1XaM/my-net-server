"""
Kafka consumer for the runner service.
Receives code execution requests, processes them, and sends responses.

Encryption scheme:
- Kafka → Runner (requests): Encrypted with CHAT_KAFKA_ENCRYPTION_KEY
- Runner → Kafka (responses): Encrypted with RUNNER_KAFKA_ENCRYPTION_KEY
"""
import os
import json
import asyncio
import logging
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError
import hashlib
import base64

logger = logging.getLogger(__name__)

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_CODE_REQUEST_TOPIC = os.getenv("KAFKA_CODE_REQUEST_TOPIC", "code-execution-requests")
KAFKA_CODE_RESPONSE_TOPIC = os.getenv("KAFKA_CODE_RESPONSE_TOPIC", "code-execution-responses")
KAFKA_CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "runner-consumer-group")

# Separate encryption keys for each direction
CHAT_KAFKA_ENCRYPTION_KEY = os.getenv("CHAT_KAFKA_ENCRYPTION_KEY", "chat-kafka-encryption-key-32b!")
RUNNER_KAFKA_ENCRYPTION_KEY = os.getenv("RUNNER_KAFKA_ENCRYPTION_KEY", "runner-kafka-encryption-key-32!")


def _derive_fernet_key(key_string: str) -> bytes:
    """Generate a valid Fernet key from an encryption key string"""
    key_hash = hashlib.sha256(key_string.encode()).digest()
    return base64.urlsafe_b64encode(key_hash)


# Fernet instances for each direction
_chat_kafka_fernet: Optional[Fernet] = None
_runner_kafka_fernet: Optional[Fernet] = None


def get_chat_kafka_fernet() -> Fernet:
    """Get Fernet instance for Chat → Kafka encryption (requests)"""
    global _chat_kafka_fernet
    if _chat_kafka_fernet is None:
        _chat_kafka_fernet = Fernet(_derive_fernet_key(CHAT_KAFKA_ENCRYPTION_KEY))
    return _chat_kafka_fernet


def get_runner_kafka_fernet() -> Fernet:
    """Get Fernet instance for Runner → Kafka encryption (responses)"""
    global _runner_kafka_fernet
    if _runner_kafka_fernet is None:
        _runner_kafka_fernet = Fernet(_derive_fernet_key(RUNNER_KAFKA_ENCRYPTION_KEY))
    return _runner_kafka_fernet


def decrypt_request(encrypted_data: bytes) -> dict:
    """Decrypt a request message (from Chat)"""
    decrypted = get_chat_kafka_fernet().decrypt(encrypted_data)
    return json.loads(decrypted.decode())


def encrypt_response(data: dict) -> bytes:
    """Encrypt a response message (Runner → Kafka)"""
    json_str = json.dumps(data)
    return get_runner_kafka_fernet().encrypt(json_str.encode())


class KafkaCodeRunner:
    """Kafka consumer that receives code execution requests and sends responses"""
    
    def __init__(self, pool_getter, static_checker=None, timeout: int = 10):
        """
        Initialize the Kafka code runner.
        
        Args:
            pool_getter: Async function to get the container pool
            static_checker: Optional static check function
            timeout: Default execution timeout
        """
        self.pool_getter = pool_getter
        self.static_checker = static_checker
        self.default_timeout = timeout
        
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumer: Optional[AIOKafkaConsumer] = None
        self._is_running = False
        self._consumer_task: Optional[asyncio.Task] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize Kafka producer and consumer"""
        if self._initialized:
            return
        
        max_retries = 5
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                # Create producer for responses
                self.producer = AIOKafkaProducer(
                    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                    value_serializer=lambda v: v,
                    max_request_size=10485760,
                    request_timeout_ms=30000,
                )
                await self.producer.start()
                logger.info(f"Kafka producer connected to {KAFKA_BOOTSTRAP_SERVERS}")
                
                # Create consumer for requests
                self.consumer = AIOKafkaConsumer(
                    KAFKA_CODE_REQUEST_TOPIC,
                    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                    group_id=KAFKA_CONSUMER_GROUP,
                    auto_offset_reset="earliest",
                    enable_auto_commit=True,
                )
                await self.consumer.start()
                logger.info(f"Kafka consumer started for topic: {KAFKA_CODE_REQUEST_TOPIC}")
                
                self._initialized = True
                return
                
            except KafkaConnectionError as e:
                logger.warning(f"Kafka connection attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    raise
    
    async def start(self):
        """Start consuming messages"""
        await self.initialize()
        self._is_running = True
        self._consumer_task = asyncio.create_task(self._consume_requests())
        logger.info("Kafka code runner started")
    
    async def stop(self):
        """Stop the consumer and producer"""
        self._is_running = False
        
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
        
        if self.consumer:
            await self.consumer.stop()
        
        if self.producer:
            await self.producer.stop()
        
        self._initialized = False
        logger.info("Kafka code runner stopped")
    
    async def _consume_requests(self):
        """Main consumer loop - processes code execution requests"""
        try:
            async for msg in self.consumer:
                if not self._is_running:
                    break
                
                try:
                    # Decrypt request using Chat's key
                    request = decrypt_request(msg.value)
                    request_id = request.get("request_id")
                    code = request.get("code", "")
                    user_id = request.get("user_id", "anonymous")
                    timeout = request.get("timeout", self.default_timeout)
                    
                    logger.info(f"Received code execution request: {request_id}")
                    
                    # Process the request
                    result = await self._execute_code(code, user_id, timeout)
                    result["request_id"] = request_id
                    
                    # Send encrypted response using Runner's key
                    encrypted_response = encrypt_response(result)
                    await self.producer.send_and_wait(
                        KAFKA_CODE_RESPONSE_TOPIC,
                        encrypted_response,
                        key=request_id.encode() if request_id else None,
                    )
                    
                    logger.info(f"Sent response for request: {request_id}")
                    
                except Exception as e:
                    logger.error(f"Error processing Kafka request: {e}")
                    # Try to send error response
                    try:
                        if "request_id" in locals() and request_id:
                            error_response = {
                                "request_id": request_id,
                                "error": str(e),
                                "status_code": 500
                            }
                            encrypted_error = encrypt_response(error_response)
                            await self.producer.send_and_wait(
                                KAFKA_CODE_RESPONSE_TOPIC,
                                encrypted_error,
                                key=request_id.encode(),
                            )
                    except Exception as send_error:
                        logger.error(f"Failed to send error response: {send_error}")
                        
        except asyncio.CancelledError:
            logger.info("Request consumer cancelled")
        except Exception as e:
            logger.error(f"Consumer loop error: {e}")
    
    async def _execute_code(self, code: str, user_id: str, timeout: int) -> Dict[str, Any]:
        """Execute code in the container pool"""
        # Static check if enabled
        if self.static_checker:
            static_issues = self.static_checker(code)
            if static_issues:
                return {
                    "error": "forbidden constructs found",
                    "details": static_issues,
                    "status_code": 403
                }
        
        try:
            pool = await self.pool_getter()
            result = await pool.execute_code(code, timeout=timeout, user_id=user_id)
            
            if "error" in result:
                status_code = result.get("status_code", 500)
                return {
                    "error": result["error"],
                    "status_code": status_code
                }
            
            return {
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "return_code": result.get("return_code", 0),
            }
            
        except Exception as e:
            logger.error(f"Code execution error: {e}")
            return {
                "error": str(e),
                "status_code": 500
            }


# Global instance (initialized in server.py)
kafka_runner: Optional[KafkaCodeRunner] = None


def create_kafka_runner(pool_getter, static_checker=None, timeout: int = 10) -> KafkaCodeRunner:
    """Create a new Kafka code runner instance"""
    global kafka_runner
    kafka_runner = KafkaCodeRunner(pool_getter, static_checker, timeout)
    return kafka_runner


def get_kafka_runner() -> Optional[KafkaCodeRunner]:
    """Get the global Kafka runner instance"""
    return kafka_runner
