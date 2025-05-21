import dotenv from 'dotenv';
import mongoose from 'mongoose';
import { createClient, RedisClientType } from 'redis';
import amqp, { Connection, Channel } from 'amqplib';

dotenv.config();

const MONGO_URI = process.env.MONGO_URI || 'mongodb://localhost:27017/nodedb';
const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379';
const RABBITMQ_URL = process.env.RABBITMQ_URL || 'amqp://guest:guest@localhost:5672';

export const connectDB = async (): Promise<void> => {
  try {
    await mongoose.connect(MONGO_URI);
    console.log('MongoDB Connected...');
  } catch (err) {
    const error = err as Error;
    console.error('MongoDB connection error:', error.message);
    process.exit(1); // Exit process with failure
  }
};

let redisClient: RedisClientType | null = null;
export const getRedisClient = async (): Promise<RedisClientType> => {
  if (redisClient && redisClient.isOpen) {
    return redisClient;
  }
  redisClient = createClient({ url: REDIS_URL });
  redisClient.on('error', (err) => console.error('Redis Client Error', err as Error));
  try {
    await redisClient.connect();
    console.log('Redis Connected...');
  } catch (err) {
    const error = err as Error;
    console.error('Redis connection error:', error);
    // Don't exit, app might still function without Redis, or retry logic could be added
  }
  return redisClient as RedisClientType; // Type assertion after successful connection or error handling
};

let rabbitMQConnection: Connection | null = null;
let rabbitMQChannel: Channel | null = null;

export const connectRabbitMQ = async (): Promise<void> => {
    try {
        if (!rabbitMQConnection || !rabbitMQChannel) { // Check if already connected
            rabbitMQConnection = await amqp.connect(RABBITMQ_URL);
            rabbitMQChannel = await rabbitMQConnection.createChannel();
            console.log('RabbitMQ Connected...');

            // Graceful shutdown
            process.once('SIGINT', async () => {
                if (rabbitMQChannel) await rabbitMQChannel.close();
                if (rabbitMQConnection) await rabbitMQConnection.close();
                console.log('RabbitMQ connection closed.');
            });
        }
    } catch (err) {
        const error = err as Error;
        console.error('RabbitMQ connection error:', error.message);
        // Depending on the app's needs, you might want to retry or exit
    }
};

export const getRabbitMQChannel = async (): Promise<Channel | null> => {
    if (!rabbitMQChannel) {
        await connectRabbitMQ(); // Ensure connection is established
    }
    return rabbitMQChannel;
};

// Initialize connections when this module is loaded
(async () => {
  await getRedisClient();
  await connectRabbitMQ();
})();
