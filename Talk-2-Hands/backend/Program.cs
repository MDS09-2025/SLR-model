using Microsoft.AspNetCore.Http.Features;
using Microsoft.AspNetCore.Server.Kestrel.Core;
using Microsoft.Extensions.FileProviders;
using Microsoft.AspNetCore.StaticFiles;
using Talk2Hands.Backend.Services;

var builder = WebApplication.CreateBuilder(args);

// Add CORS
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowAngularClient",
        policy =>
        {
            policy.WithOrigins("http://localhost:4200") // Angular dev server
                  .AllowAnyHeader()
                  .AllowAnyMethod();
        });
});

// For multipart forms (file uploads)
builder.Services.Configure<FormOptions>(options =>
{
    options.MultipartBodyLengthLimit = long.MaxValue;  // no limit on form upload
});

// For Kestrel server (global request limit)
builder.WebHost.ConfigureKestrel(serverOptions =>
{
    serverOptions.Limits.MaxRequestBodySize = long.MaxValue;
});

// Add services to the container.
// Learn more about configuring Swagger/OpenAPI at https://aka.ms/aspnetcore/swashbuckle
// Controllers
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();


// ✅ Register your DI services
builder.Services.AddSingleton<IPipelineStore, PipelineStore>();
builder.Services.AddSingleton<IPipelineQueue, PipelineQueue>();
builder.Services.AddHostedService<PipelineWorker>();

builder.Services.AddCors(o => o.AddDefaultPolicy(p =>
    p.AllowAnyOrigin().AllowAnyHeader().AllowAnyMethod()
));

var app = builder.Build();

app.Use((context, next) =>
{
    var maxBodySizeFeature = context.Features.Get<IHttpMaxRequestBodySizeFeature>();
    if (maxBodySizeFeature != null)
        maxBodySizeFeature.MaxRequestBodySize = null;

    return next();
});

app.UseCors();

// Serve everything in wwwroot
app.UseStaticFiles();

// Serve specifically /uploads
app.UseStaticFiles(new StaticFileOptions
{
    FileProvider = new PhysicalFileProvider(
        Path.Combine(builder.Environment.ContentRootPath, "wwwroot", "uploads")),
    RequestPath = "/uploads",
    ServeUnknownFileTypes = true,
    DefaultContentType = "application/octet-stream",
    ContentTypeProvider = new FileExtensionContentTypeProvider(
        new Dictionary<string, string>
        {
            { ".flac", "audio/flac" },
            { ".mp4", "video/mp4" },
            { ".webm", "video/webm" },
            { ".mov", "video/quicktime" }
        })
});


// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

// app.UseHttpsRedirection();
app.UseCors("AllowAngularClient");
app.MapControllers();
app.Run();
