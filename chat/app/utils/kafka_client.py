"""
Kafka client for message production and consumption.
Handles encrypted communication between chat and runner services.

Encryption scheme:
- Chat → Kafka (requests): Encrypted with CHAT_KAFKA_ENCRYPTION_KEY
- Kafka → Chat (responses): Encrypted with RUNNER_KAFKA_ENCRYPTION_KEY
"""
import os
import json
import asyncio
import logging
import hashlib
import base64
from typing import Optional, Dict, Any
from uuid import uuid4
from cryptography.fernet import Fernet
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError

logger = logging.getLogger(__name__)

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")  # Empty = disabled
KAFKA_CODE_REQUEST_TOPIC = os.getenv("KAFKA_CODE_REQUEST_TOPIC", "code-execution-requests")
KAFKA_CODE_RESPONSE_TOPIC = os.getenv("KAFKA_CODE_RESPONSE_TOPIC", "code-execution-responses")

# Check if Kafka is enabled (non-empty bootstrap servers)
KAFKA_ENABLED = bool(KAFKA_BOOTSTRAP_SERVERS and KAFKA_BOOTSTRAP_SERVERS.strip())

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


def encrypt_request(data: dict) -> bytes:
    """Encrypt a request message (Chat → Kafka)"""
    json_str = json.dumps(data)
    return get_chat_kafka_fernet().encrypt(json_str.encode())


def decrypt_response(encrypted_data: bytes) -> dict:
    """Decrypt a response message (Kafka → Chat, from Runner)"""
    decrypted = get_runner_kafka_fernet().decrypt(encrypted_data)
    return json.loads(decrypted.decode())


class KafkaManager:
    """Manages Kafka producer and consumer for async communication"""
    
    def __init__(self):
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumer: Optional[AIOKafkaConsumer] = None
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._consumer_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._initialized = False
    
    async def initialize(self):
        """Initialize Kafka producer and start response consumer"""
        if self._initialized:
            return
        
        # Skip if Kafka is disabled
        if not KAFKA_ENABLED:
            logger.info("Kafka is disabled (KAFKA_BOOTSTRAP_SERVERS is empty)")
            return
        
        try:
            # Create producer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: v,  # We handle serialization ourselves
                max_request_size=10485760,  # 10MB max message size
                request_timeout_ms=30000,
                retry_backoff_ms=500,
            )
            await self.producer.start()
            logger.info(f"Kafka producer connected to {KAFKA_BOOTSTRAP_SERVERS}")
            
            # Create consumer for responses
            self.consumer = AIOKafkaConsumer(
                KAFKA_CODE_RESPONSE_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id=f"chat-response-consumer-{uuid4().hex[:8]}",
                auto_offset_reset="latest",
                enable_auto_commit=True,
            )
            await self.consumer.start()
            logger.info(f"Kafka consumer started for topic: {KAFKA_CODE_RESPONSE_TOPIC}")
            
            # Start consumer task
            self._is_running = True
            self._consumer_task = asyncio.create_task(self._consume_responses())
            
            self._initialized = True
            
        except KafkaConnectionError as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown Kafka connections"""
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
        
        # Cancel all pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()
        
        self._pending_requests.clear()
        self._initialized = False
        logger.info("Kafka manager shutdown complete")
    
    async def _consume_responses(self):
        """Background task to consume code execution responses"""
        try:
            async for msg in self.consumer:
                try:
                    # Decrypt response using Runner's key
                    response = decrypt_response(msg.value)
                    request_id = response.get("request_id")
                    
                    if request_id and request_id in self._pending_requests:
                        future = self._pending_requests.pop(request_id)
                        if not future.done():
                            future.set_result(response)
                    else:
                        logger.warning(f"Received response for unknown request: {request_id}")
                        
                except Exception as e:
                    logger.error(f"Error processing Kafka response: {e}")
                    
        except asyncio.CancelledError:
            logger.info("Response consumer cancelled")
        except Exception as e:
            logger.error(f"Response consumer error: {e}")
    
    async def execute_code(self, code: str, user_id: str = "anonymous", timeout: int = 30) -> Dict[str, Any]:
        """
        Send code execution request via Kafka and wait for response.
        
        Args:
            code: Python code to execute
            user_id: User ID for tracking
            timeout: Timeout in seconds
            
        Returns:
            Execution result dictionary
        """
        if not self._initialized:
            await self.initialize()
        
        # If Kafka is disabled, raise an error so HTTP fallback can be used
        if not KAFKA_ENABLED or self.producer is None:
            raise RuntimeError("Kafka is not available")
        
        request_id = str(uuid4())
        
        # Create request message
        request = {
            "request_id": request_id,
            "code": code,
            "user_id": user_id,
            "timeout": timeout,
        }
        
        # Encrypt request using Chat's key
        encrypted_request = encrypt_request(request)
        
        # Create future for response
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future
        
        try:
            # Send to Kafka
            await self.producer.send_and_wait(
                KAFKA_CODE_REQUEST_TOPIC,
                encrypted_request,
                key=request_id.encode(),
            )
            logger.debug(f"Sent code execution request: {request_id}")
            
            # Wait for response with timeout
            result = await asyncio.wait_for(future, timeout=timeout + 5)
            return result
            
        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            return {
                "error": f"Code execution timed out after {timeout} seconds",
                "status_code": 408
            }
        except Exception as e:
            self._pending_requests.pop(request_id, None)
            logger.error(f"Error executing code via Kafka: {e}")
            return {
                "error": f"Failed to execute code: {str(e)}",
                "status_code": 500
            }


# Global Kafka manager instance
kafka_manager = KafkaManager()


async def get_kafka_manager() -> KafkaManager:
    """Get the global Kafka manager, initializing if needed"""
    if not kafka_manager._initialized:
        await kafka_manager.initialize()
    return kafka_manager
