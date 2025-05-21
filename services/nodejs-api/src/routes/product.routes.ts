import { Router, Request, Response, NextFunction } from 'express';
import Product, { IProduct } from '../models/product.model';
import { getRedisClient } from '../config/config';
import { publishProductEvent } from '../services/rabbitMQ.service';
import { RedisClientType } from 'redis';

const router = Router();
const PRODUCT_CACHE_PREFIX = 'product_';
const ALL_PRODUCTS_CACHE_KEY = 'products_all';
const CACHE_EXPIRATION_SECONDS = 300; // 5 minutes

// Middleware for Redis client
let redisClient: RedisClientType;
const ensureRedisClient = async (req: Request, res: Response, next: NextFunction) => {
    if (!redisClient || !redisClient.isOpen) {
        try {
            redisClient = await getRedisClient();
        } catch (error) {
            console.error("Failed to get Redis client in middleware:", error);
            // Optionally, you could send an error response or allow request to proceed without cache
        }
    }
    next();
};
router.use(ensureRedisClient);


/**
 * @openapi
 * /products:
 *   get:
 *     tags:
 *       - Products
 *     summary: Retrieve a list of all products
 *     description: Fetches all products from the database, uses caching.
 *     responses:
 *       200:
 *         description: A list of products.
 *         content:
 *           application/json:
 *             schema:
 *               type: array
 *               items:
 *                 $ref: '#/components/schemas/Product'
 *       500:
 *         description: Server error
 */
router.get('/products', async (req: Request, res: Response) => {
    if (!redisClient || !redisClient.isOpen) {
        console.warn('Redis client not available for GET /products');
    } else {
        try {
            const cachedProducts = await redisClient.get(ALL_PRODUCTS_CACHE_KEY);
            if (cachedProducts) {
                console.log('Cache hit for all products');
                return res.status(200).json(JSON.parse(cachedProducts));
            }
        } catch (cacheError) {
            console.error('Redis GET error for all products:', cacheError);
        }
    }

    try {
        const products = await Product.find();
        if (redisClient && redisClient.isOpen) {
            try {
                await redisClient.setEx(ALL_PRODUCTS_CACHE_KEY, CACHE_EXPIRATION_SECONDS, JSON.stringify(products));
                console.log('Cached all products');
            } catch (cacheSetError) {
                console.error('Redis SETEX error for all products:', cacheSetError);
            }
        }
        res.status(200).json(products);
    } catch (error) {
        console.error('Error fetching all products:', error);
        res.status(500).json({ message: 'Error fetching products', error: (error as Error).message });
    }
});

/**
 * @openapi
 * /products/{id}:
 *   get:
 *     tags:
 *       - Products
 *     summary: Retrieve a specific product by ID
 *     description: Fetches a single product by its ID, uses caching.
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema:
 *           type: string
 *         description: The product ID
 *     responses:
 *       200:
 *         description: Details of the product.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/Product'
 *       404:
 *         description: Product not found
 *       500:
 *         description: Server error
 */
router.get('/products/:id', async (req: Request, res: Response) => {
    const productId = req.params.id;
    const cacheKey = `${PRODUCT_CACHE_PREFIX}${productId}`;

    if (!redisClient || !redisClient.isOpen) {
        console.warn(`Redis client not available for GET /products/${productId}`);
    } else {
        try {
            const cachedProduct = await redisClient.get(cacheKey);
            if (cachedProduct) {
                console.log(`Cache hit for product ${productId}`);
                return res.status(200).json(JSON.parse(cachedProduct));
            }
        } catch (cacheError) {
            console.error(`Redis GET error for product ${productId}:`, cacheError);
        }
    }

    try {
        const product = await Product.findById(productId);
        if (!product) {
            return res.status(404).json({ message: 'Product not found' });
        }
        if (redisClient && redisClient.isOpen) {
           try {
                await redisClient.setEx(cacheKey, CACHE_EXPIRATION_SECONDS, JSON.stringify(product));
                console.log(`Cached product ${productId}`);
           } catch (cacheSetError) {
                console.error(`Redis SETEX error for product ${productId}:`, cacheSetError);
           }
        }
        res.status(200).json(product);
    } catch (error) {
        console.error(`Error fetching product ${productId}:`, error);
        res.status(500).json({ message: 'Error fetching product', error: (error as Error).message });
    }
});

/**
 * @openapi
 * /products:
 *   post:
 *     tags:
 *       - Products
 *     summary: Create a new product
 *     description: Adds a new product to the database and publishes an event.
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             $ref: '#/components/schemas/NewProduct'
 *     responses:
 *       201:
 *         description: Product created successfully.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/Product'
 *       400:
 *         description: Invalid input
 *       500:
 *         description: Server error
 */
router.post('/products', async (req: Request, res: Response) => {
    try {
        const { name, price, stock } = req.body;
        if (!name || price === undefined) {
            return res.status(400).json({ message: 'Missing required fields: name and price' });
        }

        const newProduct = new Product({ name, price, stock });
        await newProduct.save();

        if (redisClient && redisClient.isOpen) {
            try {
                await redisClient.del(ALL_PRODUCTS_CACHE_KEY); // Invalidate all products cache
                console.log('Invalidated all products cache on POST');
            } catch (cacheDelError) {
                console.error('Redis DEL error for all products cache on POST:', cacheDelError);
            }
        }
        
        publishProductEvent('product.created', newProduct.toObject());
        res.status(201).json(newProduct);
    } catch (error) {
        console.error('Error creating product:', error);
        res.status(500).json({ message: 'Error creating product', error: (error as Error).message });
    }
});

/**
 * @openapi
 * /products/{id}:
 *   put:
 *     tags:
 *       - Products
 *     summary: Update an existing product
 *     description: Updates a product by ID and invalidates relevant caches, then publishes an event.
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema:
 *           type: string
 *         description: The product ID
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             $ref: '#/components/schemas/NewProduct' 
 *     responses:
 *       200:
 *         description: Product updated successfully.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/Product'
 *       404:
 *         description: Product not found
 *       500:
 *         description: Server error
 */
router.put('/products/:id', async (req: Request, res: Response) => {
    const productId = req.params.id;
    try {
        const updatedProduct = await Product.findByIdAndUpdate(productId, req.body, { new: true, runValidators: true });
        if (!updatedProduct) {
            return res.status(404).json({ message: 'Product not found' });
        }

        if (redisClient && redisClient.isOpen) {
            try {
                await redisClient.del([`${PRODUCT_CACHE_PREFIX}${productId}`, ALL_PRODUCTS_CACHE_KEY]);
                console.log(`Invalidated cache for product ${productId} and all products on PUT`);
            } catch (cacheDelError) {
                console.error(`Redis DEL error on PUT for product ${productId}:`, cacheDelError);
            }
        }
        
        publishProductEvent('product.updated', updatedProduct.toObject());
        res.status(200).json(updatedProduct);
    } catch (error) {
        console.error(`Error updating product ${productId}:`, error);
        res.status(500).json({ message: 'Error updating product', error: (error as Error).message });
    }
});

/**
 * @openapi
 * /products/{id}:
 *   delete:
 *     tags:
 *       - Products
 *     summary: Delete a product
 *     description: Deletes a product by ID and invalidates relevant caches, then publishes an event.
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema:
 *           type: string
 *         description: The product ID
 *     responses:
 *       204:
 *         description: Product deleted successfully
 *       404:
 *         description: Product not found
 *       500:
 *         description: Server error
 */
router.delete('/products/:id', async (req: Request, res: Response) => {
    const productId = req.params.id;
    try {
        const deletedProduct = await Product.findByIdAndDelete(productId);
        if (!deletedProduct) {
            return res.status(404).json({ message: 'Product not found' });
        }

        if (redisClient && redisClient.isOpen) {
            try {
                await redisClient.del([`${PRODUCT_CACHE_PREFIX}${productId}`, ALL_PRODUCTS_CACHE_KEY]);
                console.log(`Invalidated cache for product ${productId} and all products on DELETE`);
            } catch (cacheDelError) {
                console.error(`Redis DEL error on DELETE for product ${productId}:`, cacheDelError);
            }
        }
        
        publishProductEvent('product.deleted', { Id: productId });
        res.status(204).send();
    } catch (error) {
        console.error(`Error deleting product ${productId}:`, error);
        res.status(500).json({ message: 'Error deleting product', error: (error as Error).message });
    }
});

export default router;
