from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio # Import asyncio
import json
import redis.asyncio as aioredis
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from decimal import Decimal

from . import crud, models
from .config import (
    get_mongo_db, close_mongo_db,
    get_redis_client, close_redis_client,
    get_rabbitmq_channel, close_rabbitmq_connection,
    API_TITLE, API_VERSION, API_DESCRIPTION, CONTACT_NAME, CONTACT_EMAIL,
    CACHE_EXPIRATION_SECONDS, PRODUCT_CACHE_PREFIX, ALL_PRODUCTS_CACHE_KEY
)
from .rabbitmq_service import publish_product_event, start_product_event_consumer, default_message_processor
from .models import ProductCreate, ProductUpdate, ProductResponse, ProductListResponse

# Helper for cache key generation
def get_product_cache_key(product_id: str) -> str:
    return f"{PRODUCT_CACHE_PREFIX}{product_id}"

# Context manager for application lifespan events (startup, shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Application startup...")
    # Initialize database connections
    await get_mongo_db()
    await get_redis_client() # Initialize redis client
    _conn, _channel = await get_rabbitmq_channel() # Initialize RabbitMQ connection and channel
    
    # Start RabbitMQ consumer in the background
    # Ensure this doesn't block startup; it should run as a background task
    asyncio.create_task(start_product_event_consumer(default_message_processor))
    
    # Seed data if needed (optional, can be run once manually or via a script)
    # await crud.seed_initial_products() 
    
    yield # Application is now running
    
    print("Application shutdown...")
    # Clean up resources
    await close_rabbitmq_connection()
    await close_redis_client()
    await close_mongo_db()


app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    contact={"name": CONTACT_NAME, "email": CONTACT_EMAIL},
    lifespan=lifespan
)

# Dependency for Redis client
async def get_redis_dep() -> Optional[aioredis.Redis]:
    return await get_redis_client()

@app.get("/health", tags=["General"])
async def health_check():
    return {"status": "Healthy"}

@app.get("/", tags=["General"], response_model=Dict[str, Any])
async def root():
    return {
        "Message": "Python FastAPI API is running",
        "Timestamp": datetime.now(timezone.utc).isoformat(),
        "Documentation": "/docs" 
    }

@app.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED, tags=["Products"])
async def create_new_product(
    product: ProductCreate, 
    redis: Optional[aioredis.Redis] = Depends(get_redis_dep)
):
    try:
        created_product = await crud.create_product(product)
        if redis:
            try:
                await redis.delete(ALL_PRODUCTS_CACHE_KEY)
                print(f"Cache invalidated for {ALL_PRODUCTS_CACHE_KEY} on product creation.")
            except Exception as e:
                print(f"Redis DEL error on product creation: {e}")
        
        # Publish event (convert Pydantic model to dict for publishing)
        # Ensure 'id' is stringified if it's an ObjectId in the model for RabbitMQ
        product_event_data = created_product.model_dump(mode='json') # Pydantic v2
        if '_id' in product_event_data and not isinstance(product_event_data['_id'], str):
             product_event_data['id'] = str(product_event_data.pop('_id')) # Use 'id' as key
        elif 'id' in product_event_data and not isinstance(product_event_data['id'], str):
             product_event_data['id'] = str(product_event_data['id'])

        await publish_product_event("product.created", product_event_data)
        return created_product
    except Exception as e:
        # Log the exception e
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create product: {str(e)}")

@app.get("/products", response_model=List[ProductResponse], tags=["Products"])
async def read_products(
    skip: int = 0, 
    limit: int = 100, 
    redis: Optional[aioredis.Redis] = Depends(get_redis_dep)
):
    if redis:
        try:
            cached_products = await redis.get(ALL_PRODUCTS_CACHE_KEY)
            if cached_products:
                print(f"Cache hit for {ALL_PRODUCTS_CACHE_KEY}")
                # Deserialize carefully, Pydantic List[ProductResponse] expects a list of dicts
                product_list_dict = json.loads(cached_products)
                return [ProductResponse.model_validate(p_dict) for p_dict in product_list_dict]
        except Exception as e:
            print(f"Redis GET error for {ALL_PRODUCTS_CACHE_KEY}: {e}")

    products = await crud.get_all_products(skip=skip, limit=limit)
    if redis:
        try:
            # Serialize for cache: list of dicts
            products_for_cache = [p.model_dump(mode='json') for p in products]
            await redis.setex(ALL_PRODUCTS_CACHE_KEY, CACHE_EXPIRATION_SECONDS, json.dumps(products_for_cache))
            print(f"Cached data for {ALL_PRODUCTS_CACHE_KEY}")
        except Exception as e:
            print(f"Redis SETEX error for {ALL_PRODUCTS_CACHE_KEY}: {e}")
    return products

@app.get("/products/{product_id}", response_model=ProductResponse, tags=["Products"])
async def read_product_by_id(
    product_id: str, 
    redis: Optional[aioredis.Redis] = Depends(get_redis_dep)
):
    cache_key = get_product_cache_key(product_id)
    if redis:
        try:
            cached_product = await redis.get(cache_key)
            if cached_product:
                print(f"Cache hit for product {product_id}")
                return ProductResponse.model_validate(json.loads(cached_product))
        except Exception as e:
            print(f"Redis GET error for product {product_id}: {e}")

    db_product = await crud.get_product_by_id(product_id)
    if db_product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    
    if redis:
        try:
            await redis.setex(cache_key, CACHE_EXPIRATION_SECONDS, db_product.model_dump_json()) # Pydantic v2
            print(f"Cached data for product {product_id}")
        except Exception as e:
            print(f"Redis SETEX error for product {product_id}: {e}")
    return db_product

@app.put("/products/{product_id}", response_model=ProductResponse, tags=["Products"])
async def update_existing_product(
    product_id: str, 
    product_update: ProductUpdate, 
    redis: Optional[aioredis.Redis] = Depends(get_redis_dep)
):
    updated_product = await crud.update_product_by_id(product_id, product_update)
    if updated_product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    
    if redis:
        try:
            # Invalidate specific product cache and all products list cache
            await redis.delete(get_product_cache_key(product_id))
            await redis.delete(ALL_PRODUCTS_CACHE_KEY)
            print(f"Cache invalidated for product {product_id} and {ALL_PRODUCTS_CACHE_KEY} on update.")
        except Exception as e:
            print(f"Redis DEL error on product update for {product_id}: {e}")

    product_event_data = updated_product.model_dump(mode='json')
    if '_id' in product_event_data and not isinstance(product_event_data['_id'], str):
         product_event_data['id'] = str(product_event_data.pop('_id'))
    elif 'id' in product_event_data and not isinstance(product_event_data['id'], str):
         product_event_data['id'] = str(product_event_data['id'])
         
    await publish_product_event("product.updated", product_event_data)
    return updated_product

@app.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Products"])
async def remove_product(
    product_id: str, 
    redis: Optional[aioredis.Redis] = Depends(get_redis_dep)
):
    deleted = await crud.delete_product_by_id(product_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    
    if redis:
        try:
            await redis.delete(get_product_cache_key(product_id))
            await redis.delete(ALL_PRODUCTS_CACHE_KEY)
            print(f"Cache invalidated for product {product_id} and {ALL_PRODUCTS_CACHE_KEY} on delete.")
        except Exception as e:
            print(f"Redis DEL error on product delete for {product_id}: {e}")
            
    await publish_product_event("product.deleted", {"id": product_id}) # Only ID needed for delete event
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)

# To run this app (typically from the services/python-api directory):
# uvicorn app.main:app --reload --port 8000
