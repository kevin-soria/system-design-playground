package com.example.javaapi.controller;

import com.example.javaapi.model.Product;
import com.example.javaapi.repository.ProductRepository;
import com.example.javaapi.service.RabbitMqService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.CachePut;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.cache.annotation.Caching;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/")
public class ProductController {

    private static final Logger logger = LoggerFactory.getLogger(ProductController.class);
    private static final String PRODUCT_CACHE_NAME = "products";
    private static final String ALL_PRODUCTS_CACHE_KEY = "'allProducts'"; // Note the single quotes for SpEL

    @Autowired
    private ProductRepository productRepository;

    @Autowired
    private RabbitMqService rabbitMqService;

    @GetMapping("/health")
    public ResponseEntity<String> healthCheck() {
        return ResponseEntity.ok("Healthy");
    }

    @GetMapping
    public ResponseEntity<Map<String, Object>> root() {
        Map<String, Object> response = new HashMap<>();
        response.put("Message", "Java API is running");
        response.put("Timestamp", LocalDateTime.now());
        return ResponseEntity.ok(response);
    }

    @GetMapping("/products")
    @Cacheable(value = PRODUCT_CACHE_NAME, key = ALL_PRODUCTS_CACHE_KEY)
    public List<Product> getAllProducts() {
        logger.info("Fetching all products from database");
        return productRepository.findAll();
    }

    @GetMapping("/products/{id}")
    @Cacheable(value = PRODUCT_CACHE_NAME, key = "#id")
    public ResponseEntity<Product> getProductById(@PathVariable Long id) {
        logger.info("Fetching product with id {} from database", id);
        Optional<Product> product = productRepository.findById(id);
        return product.map(ResponseEntity::ok)
                      .orElseGet(() -> ResponseEntity.notFound().build());
    }

    @PostMapping("/products")
    @Caching(evict = {
        @CacheEvict(value = PRODUCT_CACHE_NAME, key = ALL_PRODUCTS_CACHE_KEY)
    })
    public ResponseEntity<Product> createProduct(@RequestBody Product product) {
        Product savedProduct = productRepository.save(product);
        rabbitMqService.publishMessage("product_events", "product.created", savedProduct);
        return ResponseEntity.status(HttpStatus.CREATED).body(savedProduct);
    }

    @PutMapping("/products/{id}")
    @Caching(evict = {
        @CacheEvict(value = PRODUCT_CACHE_NAME, key = "#id"),
        @CacheEvict(value = PRODUCT_CACHE_NAME, key = ALL_PRODUCTS_CACHE_KEY)
    })
    @CachePut(value = PRODUCT_CACHE_NAME, key = "#id") // Updates the cache for the specific product
    public ResponseEntity<Product> updateProduct(@PathVariable Long id, @RequestBody Product productDetails) {
        Optional<Product> optionalProduct = productRepository.findById(id);
        if (optionalProduct.isPresent()) {
            Product existingProduct = optionalProduct.get();
            existingProduct.setName(productDetails.getName());
            existingProduct.setPrice(productDetails.getPrice());
            existingProduct.setStock(productDetails.getStock());
            Product updatedProduct = productRepository.save(existingProduct);
            rabbitMqService.publishMessage("product_events", "product.updated", updatedProduct);
            return ResponseEntity.ok(updatedProduct);
        } else {
            return ResponseEntity.notFound().build();
        }
    }

    @DeleteMapping("/products/{id}")
    @Caching(evict = {
        @CacheEvict(value = PRODUCT_CACHE_NAME, key = "#id"),
        @CacheEvict(value = PRODUCT_CACHE_NAME, key = ALL_PRODUCTS_CACHE_KEY)
    })
    public ResponseEntity<Void> deleteProduct(@PathVariable Long id) {
        Optional<Product> optionalProduct = productRepository.findById(id);
        if (optionalProduct.isPresent()) {
            productRepository.deleteById(id);
            Map<String, Long> messagePayload = new HashMap<>();
            messagePayload.put("Id", id);
            rabbitMqService.publishMessage("product_events", "product.deleted", messagePayload);
            return ResponseEntity.noContent().build();
        } else {
            return ResponseEntity.notFound().build();
        }
    }
}
