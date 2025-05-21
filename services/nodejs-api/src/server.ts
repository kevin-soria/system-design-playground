import express, { Application, Request, Response } from 'express';
import bodyParser from 'body-parser';
import cors from 'cors';
import dotenv from 'dotenv';
import { connectDB } from './config/config';
import { setupSwagger } from './config/swagger';
import productRoutes from './routes/product.routes';
import { startProductEventConsumer } from './services/rabbitMQ.service'; // Import RabbitMQ consumer

dotenv.config();

const app: Application = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors()); // Enable CORS for all routes
app.use(bodyParser.json()); // Parse JSON bodies
app.use(bodyParser.urlencoded({ extended: true })); // Parse URL-encoded bodies

// Database connections
connectDB(); // Connect to MongoDB
// Redis and RabbitMQ are connected via their respective modules (config.ts and rabbitMQ.service.ts)

// Swagger Documentation Setup
setupSwagger(app);

// API Routes
app.get('/health', (req: Request, res: Response) => {
  res.status(200).send('Healthy');
});

app.get('/', (req: Request, res: Response) => {
    res.status(200).json({
      message: 'Node.js/TypeScript API is running',
      timestamp: new Date().toISOString(),
      documentation: '/api-docs' 
    });
  });

app.use('/', productRoutes); // Mount product routes

// Start RabbitMQ consumer
startProductEventConsumer().catch(error => {
    console.error("Failed to start RabbitMQ consumer on server startup:", error);
});

// Start the server
app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
  console.log(`API documentation available at http://localhost:${PORT}/api-docs`);
});

export default app; // Export for testing or other purposes
