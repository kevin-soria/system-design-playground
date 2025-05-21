# Stage 1: Build the TypeScript application
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package.json and package-lock.json (or yarn.lock)
COPY package.json ./
# If you use package-lock.json or yarn.lock, copy it here as well
# COPY package-lock.json ./ 
# COPY yarn.lock ./

# Install dependencies
RUN npm install

# Copy the rest of the application code
COPY . .

# Build TypeScript to JavaScript
RUN npm run build

# Stage 2: Create a production-ready image
FROM node:18-alpine AS production

WORKDIR /app

# Copy package.json and package-lock.json for production dependencies
COPY package.json ./
# If you use package-lock.json or yarn.lock, copy it here as well for production
# COPY package-lock.json ./
# COPY yarn.lock ./


# Install only production dependencies
RUN npm install --omit=dev

# Copy built application from builder stage
COPY --from=builder /app/dist ./dist
# COPY --from=builder /app/.env ./.env # .env is usually not copied to the image; use Docker Compose for env vars

# Expose the application port
EXPOSE 3000

# Command to run the application
CMD ["node", "dist/server.js"]
