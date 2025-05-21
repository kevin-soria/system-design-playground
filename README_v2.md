# System Design Microservices Playground

This repository provides a Docker Compose environment for practicing and observing microservice patterns. It features a core "Product" API replicated across multiple technology stacks, all integrated with common backing services.

## Architecture Overview

The environment includes:

- **API Services (Product Management)**:
    - **C# API**: ASP.NET Core Minimal API using Entity Framework Core, connecting to PostgreSQL.
    - **Java API**: Spring Boot API using Spring Data JPA, connecting to PostgreSQL.
    - **Node.js/TypeScript API**: Express.js API using Mongoose, connecting to MongoDB.
    - **Python API**: FastAPI application using Motor, connecting to MongoDB.
    
    All API services feature:
    - CRUD operations for "Products".
    - Redis for caching GET requests.
    - RabbitMQ for publishing and consuming product change events (e.g., `product.created`, `product.updated`, `product.deleted`).
    - Health check and root informational endpoints.
    - OpenAPI (Swagger) documentation.

- **Data Stores**:
    - **PostgreSQL**: Relational database for C# and Java APIs.
    - **MongoDB**: NoSQL document database for Node.js and Python APIs.
- **Caching**: **Redis** instance shared by all API services.
- **Message Queue**: **RabbitMQ** for asynchronous event-driven communication between services (or for external consumers).
- **API Gateway/Load Balancer**: **Nginx** configured to route requests to the appropriate API service based on URL paths (e.g., `/api/csharp/...`, `/api/java/...`).
- **Monitoring**: Optional Prometheus/Grafana setup (currently commented out in `docker-compose.yml`).

## What You're Running

When you run `docker-compose up`, you are launching a multi-container application that simulates a microservices environment. Each API service:
- Manages "Product" data (Create, Read, Update, Delete).
- Uses Redis to cache product information, reducing database load for read operations.
- Publishes events to RabbitMQ when products are created, updated, or deleted. This allows for decoupled communication and potential integration with other (hypothetical or future) services that might need to react to product changes (e.g., an inventory service, a notification service).
- Consumes messages from a RabbitMQ queue (primarily for demonstration purposes within each service, logging received messages).
- Is accessible via the Nginx API Gateway.

This setup allows you to:
- Compare how similar functionalities are implemented across different programming languages and frameworks.
- Observe caching patterns with Redis.
- Understand event-driven architecture basics with RabbitMQ.
- See how an API Gateway (Nginx) can be used to manage access to multiple backend services.

## Getting Started

### Prerequisites

- Docker and Docker Compose installed
- Git (for cloning this repository)
- 8GB+ RAM recommended

### Basic Setup

1.  **Clone this repository**:
    ```bash
    git clone <repository_url> # Replace <repository_url> with the actual URL
    cd <repository_directory_name>
    ```

2.  **Directory Structure**:
    The project expects a certain directory structure, most of which is already provided. Ensure the following directories exist at the root if you are modifying or extending:
    ```bash
    # These should already exist with the implemented services:
    # services/csharp-api/
    # services/java-api/
    # services/nodejs-api/
    # services/python-api/
    # config/nginx/conf.d/
    # logs/nginx/ (will be created by Docker if not present)
    
    # For PostgreSQL custom init scripts (optional, as DBs are created via env var):
    mkdir -p scripts 
    
    # For optional monitoring setup:
    # mkdir -p config/prometheus
    # mkdir -p config/grafana
    ```
    The `POSTGRES_MULTIPLE_DATABASES` environment variable in `docker-compose.yml` handles the creation of `csharpdb` and `javadb` in PostgreSQL automatically. Custom scripts in the `./scripts` directory can be used for further schema initialization or data seeding if needed.

3.  **Start the environment**:
    To build and start all services (APIs, databases, Nginx, etc.):
    ```bash
    docker-compose up --build -d
    ```
    To start only the core infrastructure (databases, Redis, RabbitMQ, Nginx):
    ```bash
    docker-compose up -d postgres mongo redis rabbitmq nginx
    ```
    You can then start individual API services as needed, e.g., `docker-compose up -d csharp-api`.

### Accessing Services

-   **Nginx API Gateway**: `http://localhost` (or `http://localhost:80`)
    -   C# API: `http://localhost/api/csharp/products` (Docs: `http://localhost/api/csharp/swagger`)
    -   Java API: `http://localhost/api/java/products` (Docs: `http://localhost/api/java/swagger-ui.html`)
    -   Node.js API: `http://localhost/api/nodejs/products` (Docs: `http://localhost/api/nodejs/api-docs`)
    -   Python API: `http://localhost/api/python/products` (Docs: `http://localhost/api/python/docs`)
-   **RabbitMQ Management UI**: `http://localhost:15672` (user: `guest`, pass: `guest`)
-   **PostgreSQL**: Connect via `localhost:5432` (user: `postgres`, pass: `postgres_password`)
-   **MongoDB**: Connect via `localhost:27017`

### API Service Details

The API services (`csharp-api`, `java-api`, `nodejs-api`, `python-api`) are already implemented in their respective directories under `services/`. Each includes:
- Source code for the API.
- A `Dockerfile` for building the service image.
- Configuration files (e.g., `.env`, `application.properties`, `appsettings.json` implicitly used by C#).

The Dockerfiles provided in each service directory are used by `docker-compose` to build the images. You do not need to manually create them as per the original README's "Example API Service Implementation" section, as they are now complete.

## Scaling Up

This environment is designed to start simple and scale incrementally:

### 1. Start Individual Services
```bash
docker-compose up -d csharp-api
```

### 2. Scale Services Manually
```bash
docker-compose up -d --scale csharp-api=3 --scale nodejs-api=3
```

### 3. Enable Load Balancing
Uncomment the corresponding lines in the Nginx configuration to route traffic to multiple instances.

### 4. Enable Monitoring
Uncomment the Prometheus and Grafana sections in docker-compose.yml to enable monitoring.

## System Design Exercises

Here are some exercises you can try with this environment:

1. **Basic Microservices**: Build services that communicate with each other via REST
2. **Service Discovery**: Implement dynamic service registration/discovery
3. **Caching Strategies**: Experiment with different Redis caching approaches
4. **Message Patterns**: Implement pub/sub, request/reply, and event-driven patterns
5. **Circuit Breaking**: Add Polly or similar library to handle failures gracefully
6. **Load Testing**: Use tools like k6 to test performance under load

## Advanced Configuration

### Message Queue Cluster

For a RabbitMQ cluster, update the rabbitmq service in docker-compose.yml:

```yaml
rabbitmq:
  image: rabbitmq:3-management
  hostname: rabbit1
  environment:
    - RABBITMQ_ERLANG_COOKIE=SWQOKODSQALRPCLNMEQG
    - RABBITMQ_DEFAULT_USER=guest
    - RABBITMQ_DEFAULT_PASS=guest
    - CLUSTERED=true
```

### Database Replication

For PostgreSQL with replication, you'd need a primary and replica configuration. This requires more complex setup - see PostgreSQL documentation for details.

## Testing Fault Tolerance

Create a simple script to test system resilience:

```bash
#!/bin/bash
# chaos.sh - Simple chaos testing

# Kill a random container
kill_random() {
  CONTAINER=$(docker ps --format "{{.Names}}" | grep system-design | shuf -n 1)
  echo "Killing container: $CONTAINER"
  docker kill $CONTAINER
}

# Introduce network latency
add_latency() {
  CONTAINER=$(docker ps --format "{{.Names}}" | grep system-design | shuf -n 1)
  echo "Adding network latency to $CONTAINER"
  docker exec $CONTAINER tc qdisc add dev eth0 root netem delay 200ms
}

# Run chaos test
case $1 in
  "kill") kill_random ;;
  "latency") add_latency ;;
  *) echo "Usage: ./chaos.sh [kill|latency]" ;;
esac
```

## Conclusion

This environment allows you to practice system design concepts in a controlled but realistic setting. As you get comfortable with the basics, you can extend the configuration to incorporate more advanced patterns and technologies.
