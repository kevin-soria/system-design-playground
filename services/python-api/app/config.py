import os
from dotenv import load_dotenv
import motor.motor_asyncio
import redis.asyncio as aioredis
import aio_pika
from typing import Optional, Tuple

# Load environment variables from .env file
# __file__ is app/config.py. dirname(__file__) is app. os.path.join(..., '..') is the root of the app WORKDIR
CONFIG_PY_DIR = os.path.dirname(__file__)
PROJECT_ROOT_FROM_CONFIG = os.path.abspath(os.path.join(CONFIG_PY_DIR, '..'))
ENV_PATH = os.path.join(PROJECT_ROOT_FROM_CONFIG, '.env')
load_dotenv(ENV_PATH)
print(f"Loading .env from: {ENV_PATH}")


# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/pythondb")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "pythondb")

# Redis Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
# REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") # Add if needed

# RabbitMQ Configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
RABBITMQ_URL = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/"


# API Info
API_TITLE = os.getenv("API_TITLE", "FastAPI Product API")
API_VERSION = os.getenv("API_VERSION", "1.0.0")
API_DESCRIPTION = os.getenv("API_DESCRIPTION", "Product API with FastAPI")
CONTACT_NAME = os.getenv("CONTACT_NAME", "API Support")
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "support@example.com")


# Database Client (Motor for MongoDB)
mongo_client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
db: Optional[motor.motor_asyncio.AsyncIOMotorDatabase] = None

async def get_mongo_db() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    global mongo_client, db
    if db is None:
        mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
        db = mongo_client[MONGO_DB_NAME]
        print(f"MongoDB connected to database: {MONGO_DB_NAME}")
    return db

async def close_mongo_db():
    global mongo_client
    if mongo_client:
        mongo_client.close()
        print("MongoDB connection closed.")

# Redis Client
redis_client: Optional[aioredis.Redis] = None

async def get_redis_client() -> Optional[aioredis.Redis]:
    global redis_client
    # Attempt to connect or reconnect if client is None or seems disconnected
    if redis_client is None: # Simplified check, rely on try/except for connection status
        try:
            redis_client = aioredis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}")
            await redis_client.ping() # Verify connection
            print("Redis connected.")
        except Exception as e:
            print(f"Redis connection error: {e}")
            redis_client = None # Ensure client is None if connection fails
    elif not await redis_client.ping(): # Check if existing client is still connected
        print("Redis client found, but ping failed. Attempting to reconnect.")
        try:
            await redis_client.close() # Close existing broken client
        except: # nosec
            pass # Ignore errors on close
        try:
            redis_client = aioredis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}")
            await redis_client.ping()
            print("Redis reconnected.")
        except Exception as e:
            print(f"Redis reconnection error: {e}")
            redis_client = None
    return redis_client

async def close_redis_client():
    global redis_client
    if redis_client:
        await redis_client.close()
        print("Redis connection closed.")

# RabbitMQ Client
rabbitmq_connection: Optional[aio_pika.RobustConnection] = None
rabbitmq_channel: Optional[aio_pika.Channel] = None

async def get_rabbitmq_channel() -> Tuple[Optional[aio_pika.RobustConnection], Optional[aio_pika.Channel]]:
    global rabbitmq_connection, rabbitmq_channel
    if rabbitmq_channel is None or rabbitmq_channel.is_closed:
        try:
            rabbitmq_connection = await aio_pika.connect_robust(RABBITMQ_URL)
            rabbitmq_channel = await rabbitmq_connection.channel()
            print("RabbitMQ connected and channel opened.")
        except Exception as e:
            print(f"RabbitMQ connection error: {e}")
            rabbitmq_connection = None # Ensure they are None if connection fails
            rabbitmq_channel = None
    return rabbitmq_connection, rabbitmq_channel

async def close_rabbitmq_connection():
    global rabbitmq_connection, rabbitmq_channel
    if rabbitmq_channel and not rabbitmq_channel.is_closed:
        await rabbitmq_channel.close()
        print("RabbitMQ channel closed.")
    if rabbitmq_connection and not rabbitmq_connection.is_closed:
        await rabbitmq_connection.close()
        print("RabbitMQ connection closed.")

# Cache settings
CACHE_EXPIRATION_SECONDS = 300  # 5 minutes
PRODUCT_CACHE_PREFIX = "py_product_"
ALL_PRODUCTS_CACHE_KEY = "py_products_all"

# RabbitMQ settings
PRODUCT_EXCHANGE = "product_events"
NOTIFICATION_QUEUE = "python_notifications" # Unique queue for this service
