package com.example.javaapi.consumer;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.core.ExchangeTypes;
import org.springframework.amqp.rabbit.annotation.Exchange;
import org.springframework.amqp.rabbit.annotation.Queue;
import org.springframework.amqp.rabbit.annotation.QueueBinding;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

@Component
public class RabbitMqConsumer {

    private static final Logger logger = LoggerFactory.getLogger(RabbitMqConsumer.class);

    public static final String EXCHANGE_NAME = "product_events";
    public static final String QUEUE_NAME = "java_notifications";

    @RabbitListener(bindings = @QueueBinding(
            value = @Queue(value = QUEUE_NAME, durable = "true"),
            exchange = @Exchange(value = EXCHANGE_NAME, type = ExchangeTypes.TOPIC, durable = "true"),
            key = "#" // Listen to all routing keys
    ))
    public void receiveMessage(String message) {
        logger.info("Received message from {}: {}", QUEUE_NAME, message);
        // Process message here (e.g., send notifications, update other services)
    }
}
