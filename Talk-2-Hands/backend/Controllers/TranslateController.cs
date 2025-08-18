using Microsoft.AspNetCore.Mvc;

namespace Talk2Hands.Backend.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class TranslateController : ControllerBase
    {
        private readonly IWebHostEnvironment _env;

        public TranslateController(IWebHostEnvironment env)
        {
            _env = env;
        }

        [HttpPost("link")]
        public IActionResult TranslateFromLink([FromBody] LinkRequest request)
        {
            return Ok(new { message = $"Got link: {request.Url}"});
        }

        [HttpPost("upload")]
        [DisableRequestSizeLimit] 
        [RequestSizeLimit(long.MaxValue)]
        [RequestFormLimits(MultipartBodyLengthLimit = long.MaxValue)]
        public IActionResult TranslateFromUpload([FromForm] IFormFile uploadedFile)
        {
            if (uploadedFile == null || uploadedFile.Length == 0)
                return BadRequest("No file uploaded.");

            var uploadsPath = Path.Combine(_env.ContentRootPath, "wwwroot", "uploads");
            if (!Directory.Exists(uploadsPath))
                Directory.CreateDirectory(uploadsPath);

            var filePath = Path.Combine(uploadsPath, uploadedFile.FileName);
            Console.WriteLine("Saving file to: " + filePath);
            using (var stream = new FileStream(filePath, FileMode.Create))
            {
                uploadedFile.CopyTo(stream);
            }

            var fileUrl = $"{Request.Scheme}://{Request.Host}/uploads/{uploadedFile.FileName}";

            return Ok(new { 
                message = "File uploaded successfully",
                type = uploadedFile.ContentType.StartsWith("video") ? "video" : "audio",
                backend = fileUrl
            });
        }
    }

    public class LinkRequest
    {
        public string Url { get; set; } = string.Empty;
    }
}