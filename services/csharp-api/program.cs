using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Caching.Distributed;
using Microsoft.EntityFrameworkCore;
using System;
using System.Text.Json;
using System.Threading.Tasks;
using System.Collections.Generic;
using RabbitMQ.Client;
using RabbitMQ.Client.Events;
using System.Text;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

// Configure database context
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("DefaultConnection")));

// Configure Redis cache
builder.Services.AddStackExchangeRedisCache(options =>
{
    options.Configuration = builder.Configuration["REDIS_CONNECTION"];
    options.InstanceName = "CSharpApi_";
});

// Configure RabbitMQ 
builder.Services.AddSingleton<IRabbitMqService, RabbitMqService>();

var app = builder.Build();

// Configure the HTTP request pipeline
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

// Health check endpoint
app.MapGet("/health", () => "Healthy");

// Basic API endpoints
app.MapGet("/", () => new { Message = "C# API is running", Timestamp = DateTime.UtcNow });

// Product endpoints with caching demonstration
app.MapGet("/products", async (AppDbContext db, IDistributedCache cache) =>
{
    const string cacheKey = "products_all";
    
    // Try to get from cache first
    var cachedData = await cache.GetStringAsync(cacheKey);
    if (!string.IsNullOrEmpty(cachedData))
    {
        return Results.Ok(JsonSerializer.Deserialize<List<Product>>(cachedData));
    }
    
    // If not in cache, get from database
    var products = await db.Products.ToListAsync();
    
    // Store in cache for 5 minutes
    await cache.SetStringAsync(
        cacheKey, 
        JsonSerializer.Serialize(products),
        new DistributedCacheEntryOptions { AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(5) }
    );
    
    return Results.Ok(products);
});

app.MapGet("/products/{id}", async (int id, AppDbContext db, IDistributedCache cache) =>
{
    var cacheKey = $"product_{id}";
    
    // Try to get from cache first
    var cachedData = await cache.GetStringAsync(cacheKey);
    if (!string.IsNullOrEmpty(cachedData))
    {
        return Results.Ok(JsonSerializer.Deserialize<Product>(cachedData));
    }
    
    // If not in cache, get from database
    var product = await db.Products.FindAsync(id);
    if (product == null)
    {
        return Results.NotFound();
    }
    
    // Store in cache for 5 minutes
    await cache.SetStringAsync(
        cacheKey, 
        JsonSerializer.Serialize(product),
        new DistributedCacheEntryOptions { AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(5) }
    );
    
    return Results.Ok(product);
});

app.MapPost("/products", async (Product product, AppDbContext db, IRabbitMqService rabbitMqService) =>
{
    db.Products.Add(product);
    await db.SaveChangesAsync();
    
    // Publish event to RabbitMQ
    rabbitMqService.PublishMessage("product_events", "product.created", JsonSerializer.Serialize(product));
    
    return Results.Created($"/products/{product.Id}", product);
});

app.MapPut("/products/{id}", async (int id, Product updatedProduct, AppDbContext db, IDistributedCache cache, IRabbitMqService rabbitMqService) =>
{
    var product = await db.Products.FindAsync(id);
    if (product == null)
    {
        return Results.NotFound();
    }
    
    product.Name = updatedProduct.Name;
    product.Price = updatedProduct.Price;
    product.Stock = updatedProduct.Stock;
    
    await db.SaveChangesAsync();
    
    // Invalidate cache
    await cache.RemoveAsync($"product_{id}");
    await cache.RemoveAsync("products_all");
    
    // Publish event to RabbitMQ
    rabbitMqService.PublishMessage("product_events", "product.updated", JsonSerializer.Serialize(product));
    
    return Results.Ok(product);
});

app.MapDelete("/products/{id}", async (int id, AppDbContext db, IDistributedCache cache, IRabbitMqService rabbitMqService) =>
{
    var product = await db.Products.FindAsync(id);
    if (product == null)
    {
        return Results.NotFound();
    }
    
    db.Products.Remove(product);
    await db.SaveChangesAsync();
    
    // Invalidate cache
    await cache.RemoveAsync($"product_{id}");
    await cache.RemoveAsync("products_all");
    
    // Publish event to RabbitMQ
    rabbitMqService.PublishMessage("product_events", "product.deleted", JsonSerializer.Serialize(new { Id = id }));
    
    return Results.NoContent();
});

// Start message consumer
using (var scope = app.Services.CreateScope())
{
    var rabbitMqService = scope.ServiceProvider.GetRequiredService<IRabbitMqService>();
    rabbitMqService.StartConsumingMessages("notifications", "product_events", message =>
    {
        Console.WriteLine($"Received message: {message}");
        // Process message here
    });
}

app.Run();

// Database models
public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }
    
    public DbSet<Product> Products { get; set; }
    
    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        // Seed data for testing
        modelBuilder.Entity<Product>().HasData(
            new Product { Id = 1, Name = "Product 1", Price = 10.99m, Stock = 100 },
            new Product { Id = 2, Name = "Product 2", Price = 20.99m, Stock = 50 },
            new Product { Id = 3, Name = "Product 3", Price = 30.99m, Stock = 75 }
        );
    }
}

public class Product
{
    public int Id { get; set; }
    public string Name { get; set; }
    public decimal Price { get; set; }
    public int Stock { get; set; }
}

// RabbitMQ Service
public interface IRabbitMqService
{
    void PublishMessage(string exchange, string routingKey, string message);
    void StartConsumingMessages(string queueName, string exchangeName, Action<string> messageHandler);
}

public class RabbitMqService : IRabbitMqService, IDisposable
{
    private readonly IConnection _connection;
    private readonly IModel _channel;
    
    public RabbitMqService(IConfiguration configuration)
    {
        var factory = new ConnectionFactory
        {
            HostName = configuration["RABBITMQ_HOST"],
            UserName = configuration["RABBITMQ_USER"],
            Password = configuration["RABBITMQ_PASSWORD"]
        };
        
        try
        {
            _connection = factory.CreateConnection();
            _channel = _connection.CreateModel();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"RabbitMQ connection error: {ex.Message}");
            // In a real app, you might want to implement retry logic or use a circuit breaker
        }
    }
    
    public void PublishMessage(string exchange, string routingKey, string message)
    {
        try
        {
            _channel.ExchangeDeclare(exchange, ExchangeType.Topic, durable: true);
            
            var body = Encoding.UTF8.GetBytes(message);
            
            _channel.BasicPublish(
                exchange: exchange,
                routingKey: routingKey,
                basicProperties: null,
                body: body);
                
            Console.WriteLine($"Published message to {exchange}/{routingKey}: {message}");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error publishing message: {ex.Message}");
        }
    }
    
    public void StartConsumingMessages(string queueName, string exchangeName, Action<string> messageHandler)
    {
        try
        {
            _channel.ExchangeDeclare(exchangeName, ExchangeType.Topic, durable: true);
            _channel.QueueDeclare(queueName, durable: true, exclusive: false, autoDelete: false);
            _channel.QueueBind(queueName, exchangeName, "#");
            
            var consumer = new EventingBasicConsumer(_channel);
            consumer.Received += (model, ea) =>
            {
                var body = ea.Body.ToArray();
                var message = Encoding.UTF8.GetString(body);
                
                messageHandler(message);
                
                _channel.BasicAck(ea.DeliveryTag, false);
            };
            
            _channel.BasicConsume(queueName, false, consumer);
            
            Console.WriteLine($"Started consuming messages from {queueName}");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error starting consumer: {ex.Message}");
        }
    }
    
    public void Dispose()
    {
        _channel?.Close();
        _connection?.Close();
    }
}
