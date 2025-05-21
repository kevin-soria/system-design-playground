import asyncio
import json
import aio_pika
from typing import Optional, Callable, Awaitable
from .config import get_rabbitmq_channel, PRODUCT_EXCHANGE, NOTIFICATION_QUEUE
from .models import ProductEvent, ProductEventData # Pydantic models for event structure
from decimal import Decimal

# Custom JSON encoder to handle Decimal and other types if necessary
class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, ProductEventData): # Ensure nested Pydantic models are dicts
             return obj.model_dump(mode='json')
        if hasattr(obj, 'model_dump'): # General Pydantic model handling
            return obj.model_dump(mode='json')
        return super().default(obj)

async def publish_product_event(event_type: str, product_data: dict):
    """
    Publishes a product event to RabbitMQ.
    product_data should be a dictionary representation of the product.
    """
    _conn, channel = await get_rabbitmq_channel() # Connection stored in config, channel is what we use
    
    if not channel or channel.is_closed:
        print("RabbitMQ channel is not available or closed. Cannot publish event.")
        return

    try:
        # Ensure the exchange exists
        exchange = await channel.declare_exchange(
            PRODUCT_EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
        )
        
        # Construct the message using Pydantic model for validation and structure
        # Ensure product_data is compatible with ProductEventData
        # If product_data comes directly from a Pydantic model (e.g. ProductResponse),
        # use model_dump() before passing. If it's already a dict, ensure keys match.
        
        # We expect product_data to be a dict here, convert to ProductEventData
        event_data_model = ProductEventData(**product_data)
        
        event_message = ProductEvent(event_type=event_type, data=event_data_model)
        
        message_body = json.dumps(event_message.model_dump(mode='json'), cls=CustomEncoder) # Pydantic v2
        
        message = aio_pika.Message(
            body=message_body.encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        
        routing_key = f"product.{event_type.split('.')[-1]}" # e.g. product.created
        await exchange.publish(message, routing_key=routing_key)
        print(f"Sent event [{routing_key}]: {message_body} to exchange {PRODUCT_EXCHANGE}")

    except Exception as e:
        print(f"Failed to publish product event: {e}")
        # Consider more robust error handling/retry logic here

async def start_product_event_consumer(message_handler: Callable[[dict], Awaitable[None]]):
    """
    Starts a consumer for product events from RabbitMQ.
    message_handler will be called with the deserialized message content (dict).
    """
    _conn, channel = await get_rabbitmq_channel()

    if not channel or channel.is_closed:
        print("RabbitMQ channel is not available or closed. Cannot start consumer.")
        return

    try:
        exchange = await channel.declare_exchange(
            PRODUCT_EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await channel.declare_queue(NOTIFICATION_QUEUE, durable=True)
        
        # Bind queue to the exchange to receive all product events
        await queue.bind(exchange, routing_key="#") # Listen to all routing keys under product_events

        print(f"[*] Waiting for messages in {NOTIFICATION_QUEUE}. To exit press CTRL+C")

        async def on_message(message: aio_pika.IncomingMessage):
            async with message.process(): # Acknowledges message automatically on success
                try:
                    print(f"[Python Consumer] Received message from {message.exchange}/{message.routing_key}")
                    # Deserialize the message content
                    content = json.loads(message.body.decode())
                    # Validate with Pydantic if needed, e.g. ProductEvent(**content)
                    await message_handler(content) # Pass the dict to the handler
                except json.JSONDecodeError:
                    print("Error decoding JSON message body.")
                except Exception as e:
                    print(f"Error processing message: {e}")
                    # Optionally, you could reject or nack the message if processing fails permanently

        await queue.consume(on_message)
        print(f"Consumer started for queue {NOTIFICATION_QUEUE} bound to exchange {PRODUCT_EXCHANGE}")
        
        # Keep the consumer running (FastAPI runs in its own asyncio loop)
        # If this were a standalone script, you'd need something like:
        # loop = asyncio.get_event_loop()
        # await loop.create_future() 

    except Exception as e:
        print(f"Failed to start product event consumer: {e}")

async def default_message_processor(message_content: dict):
    """ Default handler for received messages if none is provided. """
    print(f"Default processor received: {message_content}")
    # Implement actual processing logic here, e.g., logging, updating other systems

# Example of how to start the consumer (typically called from main.py or on app startup)
# async def main():
#     await start_product_event_consumer(default_message_processor)
#     # Keep alive if this is the main execution point
#     # await asyncio.Event().wait() 
# if __name__ == "__main__":
# asyncio.run(main())
