import swaggerJsdoc from 'swagger-jsdoc';
import swaggerUi from 'swagger-ui-express';
import { Express } from 'express';
import dotenv from 'dotenv';

dotenv.config();

const options: swaggerJsdoc.Options = {
  definition: {
    openapi: '3.0.0',
    info: {
      title: 'Node.js API',
      version: process.env.API_VERSION || '1.0.0',
      description: process.env.API_DESCRIPTION || 'A simple CRUD API application made with Express and documented with Swagger',
      contact: {
        name: 'API Support',
        email: process.env.API_CONTACT_EMAIL || 'support@example.com',
      },
    },
    servers: [
      {
        url: `http://localhost:${process.env.PORT || 3000}`,
        description: 'Development server',
      },
    ],
    components: {
      schemas: {
        Product: {
          type: 'object',
          required: ['name', 'price'],
          properties: {
            _id: {
              type: 'string',
              description: 'The auto-generated id of the product',
              readOnly: true,
            },
            name: {
              type: 'string',
              description: 'Name of the product',
            },
            price: {
              type: 'number',
              format: 'float',
              description: 'Price of the product',
            },
            stock: {
              type: 'number',
              description: 'Available stock of the product',
              default: 0,
            },
            createdAt: {
                type: 'string',
                format: 'date-time',
                description: 'Timestamp of creation',
                readOnly: true,
            },
            updatedAt: {
                type: 'string',
                format: 'date-time',
                description: 'Timestamp of last update',
                readOnly: true,
            }
          },
          example: {
            _id: '60c72b2f9b1e8a5f68d672c3',
            name: 'Sample Product',
            price: 19.99,
            stock: 100,
            createdAt: '2023-01-01T12:00:00.000Z',
            updatedAt: '2023-01-01T12:30:00.000Z'
          },
        },
        NewProduct: {
            type: 'object',
            required: ['name', 'price'],
            properties: {
              name: {
                type: 'string',
                description: 'Name of the product',
              },
              price: {
                type: 'number',
                format: 'float',
                description: 'Price of the product',
              },
              stock: {
                type: 'number',
                description: 'Available stock of the product',
                default: 0,
              },
            },
            example: {
              name: 'New Sample Product',
              price: 29.99,
              stock: 50,
            },
          },
      },
    },
  },
  // Path to the API docs
  // Note: You'll need to create JSDoc comments in your route files for this to work
  apis: ['./src/routes/*.ts', './src/models/*.ts'], 
};

const specs = swaggerJsdoc(options);

export const setupSwagger = (app: Express): void => {
  app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(specs, { explorer: true }));
  console.log(`Swagger docs available at /api-docs`);
};
