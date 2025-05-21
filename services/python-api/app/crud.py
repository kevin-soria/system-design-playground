from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
from bson import ObjectId
from typing import List, Optional, Dict, Any
from .models import ProductCreate, ProductUpdate, ProductResponse
from .config import get_mongo_db
from datetime import datetime
import json # For converting Decimal to float for MongoDB
from decimal import Decimal

# Helper to convert Pydantic model to dict, handling Decimal for MongoDB
def product_to_mongo_dict(product: ProductCreate | ProductUpdate) -> Dict[str, Any]:
    data = product.model_dump(exclude_unset=True) # Pydantic v2
    if 'price' in data and isinstance(data['price'], Decimal):
        data['price'] = float(data['price']) # Convert Decimal to float for MongoDB
    return data

async def get_product_collection() -> AsyncIOMotorCollection:
    db = await get_mongo_db()
    return db["products"]

async def create_product(product_data: ProductCreate) -> ProductResponse:
    collection = await get_product_collection()
    product_dict = product_to_mongo_dict(product_data)
    
    # Add timestamps
    now = datetime.utcnow()
    product_dict["created_at"] = now
    product_dict["updated_at"] = now
    
    result = await collection.insert_one(product_dict)
    created_product_doc = await collection.find_one({"_id": result.inserted_id})
    if created_product_doc:
        return ProductResponse.model_validate(created_product_doc) # Pydantic v2
    raise Exception("Failed to create product or retrieve after creation")


async def get_product_by_id(product_id: str) -> Optional[ProductResponse]:
    collection = await get_product_collection()
    if not ObjectId.is_valid(product_id):
        return None
    product_doc = await collection.find_one({"_id": ObjectId(product_id)})
    if product_doc:
        return ProductResponse.model_validate(product_doc) # Pydantic v2
    return None

async def get_all_products(skip: int = 0, limit: int = 100) -> List[ProductResponse]:
    collection = await get_product_collection()
    products_cursor = collection.find().skip(skip).limit(limit)
    products_list = []
    async for product_doc in products_cursor:
        products_list.append(ProductResponse.model_validate(product_doc)) # Pydantic v2
    return products_list

async def update_product_by_id(product_id: str, product_update_data: ProductUpdate) -> Optional[ProductResponse]:
    collection = await get_product_collection()
    if not ObjectId.is_valid(product_id):
        return None
        
    update_data = product_to_mongo_dict(product_update_data)
    
    if not update_data: # No fields to update
        # Optionally, fetch and return the existing product or return None/error
        existing_product = await get_product_by_id(product_id)
        return existing_product

    update_data["updated_at"] = datetime.utcnow()

    result = await collection.find_one_and_update(
        {"_id": ObjectId(product_id)},
        {"$set": update_data},
        return_document=True # motor uses pymongo.ReturnDocument.AFTER implicitly
    )
    if result:
        return ProductResponse.model_validate(result) # Pydantic v2
    return None

async def delete_product_by_id(product_id: str) -> bool:
    collection = await get_product_collection()
    if not ObjectId.is_valid(product_id):
        return False
    result = await collection.delete_one({"_id": ObjectId(product_id)})
    return result.deleted_count > 0

async def seed_initial_products():
    """Seeds the database with a few initial products if the collection is empty."""
    collection = await get_product_collection()
    count = await collection.count_documents({})
    if count == 0:
        print("No products found, seeding initial data...")
        products_to_seed = [
            ProductCreate(name="Python Product 1", price=Decimal("10.99"), stock=100),
            ProductCreate(name="Python Product 2", price=Decimal("20.50"), stock=50),
            ProductCreate(name="Python Product 3", price=Decimal("5.75"), stock=200),
        ]
        for prod_create in products_to_seed:
            await create_product(prod_create)
        print(f"Seeded {len(products_to_seed)} products.")
    else:
        print(f"Found {count} products, no seeding needed.")
