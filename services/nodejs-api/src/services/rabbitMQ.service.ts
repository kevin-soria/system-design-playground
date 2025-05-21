import { Channel } from 'amqplib';
import { getRabbitMQChannel } from '../config/config';

const PRODUCT_EXCHANGE = 'product_events';
const NOTIFICATION_QUEUE = 'nodejs_notifications'; // Unique queue for this service

export const publishProductEvent = async (routingKey: string, message: any): Promise<void> => {
  const channel = await getRabbitMQChannel();
  if (channel) {
    try {
      await channel.assertExchange(PRODUCT_EXCHANGE, 'topic', { durable: true });
      channel.publish(PRODUCT_EXCHANGE, routingKey, Buffer.from(JSON.stringify(message)));
      console.log(`Sent event [${routingKey}]: ${JSON.stringify(message)} to exchange ${PRODUCT_EXCHANGE}`);
    } catch (error) {
      console.error('Failed to publish product event:', error);
      // Add more robust error handling/retry logic if needed
    }
  } else {
    console.error('RabbitMQ channel not available for publishing.');
  }
};

export const startProductEventConsumer = async (): Promise<void> => {
  const channel = await getRabbitMQChannel();
  if (channel) {
    try {
      await channel.assertExchange(PRODUCT_EXCHANGE, 'topic', { durable: true });
      const q = await channel.assertQueue(NOTIFICATION_QUEUE, { durable: true });
      console.log(`[*] Waiting for messages in ${q.queue}. To exit press CTRL+C`);

      // Bind queue to the exchange with a wildcard routing key to get all product events
      await channel.bindQueue(q.queue, PRODUCT_EXCHANGE, '#'); 

      channel.consume(q.queue, (msg: import('amqplib').ConsumeMessage | null) => {
        if (msg !== null) {
          console.log(`[NodeJS Consumer] Received message from ${PRODUCT_EXCHANGE}: ${msg.content.toString()}`);
          // Add your message processing logic here
          // For example, sending a notification, updating another system, etc.
          channel.ack(msg);
        }
      });
    } catch (error) {
      console.error('Failed to start product event consumer:', error);
    }
  } else {
    console.error('RabbitMQ channel not available for consuming.');
  }
};

// Initialize consumer when this module is loaded
// (async () => {
//   await startProductEventConsumer();
// })();
// We will call startProductEventConsumer from server.ts after app setup
