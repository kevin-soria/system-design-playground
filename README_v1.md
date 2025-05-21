# System Design Practice Environment

This repository provides a Docker Compose environment for practicing system design concepts locally, allowing you to experiment with distributed systems patterns without needing production environments or cloud infrastructure.

## Architecture Overview

The environment includes:

- **API Services**: Implementations in multiple languages (C#, Java, Node.js, Python)
- **Data Stores**: Both relational (PostgreSQL) and NoSQL (MongoDB)
- **Caching**: Redis instance
- **Message Queues**: RabbitMQ (with optional Kafka)
- **API Gateway/Load Balancer**: Nginx
- **Monitoring**: Optional Prometheus/Grafana setup

## Getting Started

### Prerequisites

- Docker and Docker Compose installed
- Git (for cloning this repository)
- 8GB+ RAM recommended

### Basic Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/system-design-playground.git
   cd system-design-playground
   ```

2. Create the required directory structure:
   ```bash
   mkdir -p services/{csharp-api,java-api,nodejs-api,python-api}
   mkdir -p config/{nginx,prometheus,grafana}
   mkdir -p logs/nginx
   mkdir -p scripts
   ```

3. Create a script to initialize multiple PostgreSQL databases:
   ```bash
   # Create scripts/create-multiple-databases.sh
   echo '#!/bin/bash
   set -e
   set -u

   function create_user_and_database() {
       local database=$1
       echo "Creating database $database"
       psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
           CREATE DATABASE $database;
           GRANT ALL PRIVILEGES ON DATABASE $database TO $POSTGRES_USER;
   EOSQL
   }

   if [ -n "$POSTGRES_MULTIPLE_DATABASES" ]; then
       for db in $(echo $POSTGRES_MULTIPLE_DATABASES | tr "," " "); do
           create_user_and_database $db
       done
   fi' > scripts/create-multiple-databases.sh
   
   chmod +x scripts/create-multiple-databases.sh
   ```

4. Start the environment with minimal services:
   ```bash
   docker-compose up -d postgres mongo redis rabbitmq nginx
   ```

### API Service Implementation

Create simple API services in each language directory. For example:

#### Example C# API (services/csharp-api/Dockerfile):
```Dockerfile
FROM mcr.microsoft.com/dotnet/sdk:7.0 AS build
WORKDIR /app

COPY *.csproj ./
RUN dotnet restore

COPY . ./
RUN dotnet publish -c Release -o out

FROM mcr.microsoft.com/dotnet/aspnet:7.0
WORKDIR /app
COPY --from=build /app/out .
ENTRYPOINT ["dotnet", "csharp-api.dll"]
```

#### Node.js API (services/nodejs-api/Dockerfile):
```Dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 3000
CMD ["node", "app.js"]
```

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
