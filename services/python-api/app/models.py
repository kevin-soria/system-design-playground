from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
import uuid # For potential future use if _id is not from Mongo

# For MongoDB _id field, which is an ObjectId, but often represented as str in Pydantic
# We can create a custom type or use a Field alias if needed, but for simplicity,
# we'll often use str and handle conversion if necessary.
# Pydantic v2 handles ObjectId from MongoDB more gracefully with `model_dump(mode='json')`.

class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, field_info): # field_info is for Pydantic v2
        if not isinstance(v, (str, uuid.UUID)) and not hasattr(v, 'is_valid'): # Basic check for ObjectId-like
             # A more robust check for ObjectId would be `if not ObjectId.is_valid(str(v)):`
             # but that requires importing bson.ObjectId which we try to avoid in pure Pydantic models
            if not isinstance(v, str) or not len(v) == 24: # Basic check for typical ObjectId string length
                 # This is a simplified check. For true ObjectId validation, you'd use bson.objectid.ObjectId.is_valid
                pass # Allow it for now, FastAPI/Motor might handle it. Or raise ValueError.
        return str(v)

    @classmethod
    def __modify_schema__(cls, field_schema): # Pydantic v1 style
        field_schema.update(type="string", example="60c72b2f9b1e8a5f68d672c3")
    
    # For Pydantic v2, you might use `json_schema_extra` in the Field or model config.


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, example="Awesome Gadget")
    price: Decimal = Field(..., gt=0, example=19.99)
    stock: int = Field(default=0, ge=0, example=100)

    @validator('price', pre=True, always=True)
    def price_to_decimal(cls, v):
        if isinstance(v, float):
            return Decimal(str(v))
        if isinstance(v, str):
            try:
                return Decimal(v)
            except:
                raise ValueError("Invalid price format")
        if isinstance(v, Decimal):
            return v
        raise TypeError("Price must be a float, string, or Decimal")

class ProductCreate(ProductBase):
    pass

class ProductUpdate(ProductBase):
    name: Optional[str] = Field(None, min_length=1, example="Updated Gadget")
    price: Optional[Decimal] = Field(None, gt=0, example=29.99)
    stock: Optional[int] = Field(None, ge=0, example=150)

class ProductInDBBase(ProductBase):
    id: PyObjectId = Field(alias="_id", default_factory=lambda: str(uuid.uuid4()), example="60c72b2f9b1e8a5f68d672c3") # Using str for _id
    created_at: datetime = Field(default_factory=datetime.utcnow, example=datetime.utcnow().isoformat())
    updated_at: datetime = Field(default_factory=datetime.utcnow, example=datetime.utcnow().isoformat())
    
    class Config:
        from_attributes = True # Pydantic v2 (formerly orm_mode = True)
        populate_by_name = True # Allows use of alias "_id" for "id"
        json_encoders = {
            Decimal: lambda v: float(v), # Serialize Decimal as float in JSON responses
            datetime: lambda dt: dt.isoformat(),
            PyObjectId: lambda oid: str(oid) # Ensure PyObjectId is str in JSON
        }

class ProductResponse(ProductInDBBase):
    pass

class ProductListResponse(BaseModel):
    products: List[ProductResponse]

# For RabbitMQ messages
class ProductEventData(BaseModel):
    id: Optional[PyObjectId] = None # For delete, only ID might be present
    name: Optional[str] = None
    price: Optional[Decimal] = None
    stock: Optional[int] = None

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v) # Ensure Decimal is float for JSON message
        }

class ProductEvent(BaseModel):
    event_type: str # e.g., "product.created", "product.updated", "product.deleted"
    data: ProductEventData
