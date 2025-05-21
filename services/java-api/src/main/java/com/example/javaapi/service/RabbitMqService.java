package com.example.javaapi.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class RabbitMqService {

    private static final Logger logger = LoggerFactory.getLogger(RabbitMqService.class);
    private final RabbitTemplate rabbitTemplate;
    private final ObjectMapper objectMapper;

    @Autowired
    public RabbitMqService(RabbitTemplate rabbitTemplate, ObjectMapper objectMapper) {
        this.rabbitTemplate = rabbitTemplate;
        this.objectMapper = objectMapper;
    }

    public void publishMessage(String exchange, String routingKey, Object messagePayload) {
        try {
            String messageJson = objectMapper.writeValueAsString(messagePayload);
            rabbitTemplate.convertAndSend(exchange, routingKey, messageJson);
            logger.info("Published message to {}/{}: {}", exchange, routingKey, messageJson);
        } catch (JsonProcessingException e) {
            logger.error("Error serializing message payload to JSON", e);
        } catch (Exception e) {
            logger.error("Error publishing message to RabbitMQ", e);
        }
    }
}
