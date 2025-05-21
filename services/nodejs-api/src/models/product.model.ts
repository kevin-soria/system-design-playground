import mongoose, { Schema, Document } from 'mongoose';

export interface IProduct extends Document {
  name: string;
  price: number;
  stock: number;
}

const ProductSchema: Schema = new Schema({
  name: { type: String, required: true },
  price: { type: Number, required: true },
  stock: { type: Number, required: true, default: 0 },
}, { timestamps: true }); // Add timestamps for createdAt and updatedAt

export default mongoose.model<IProduct>('Product', ProductSchema);
