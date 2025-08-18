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
            return Ok(new { message = $"Got link: {request.Url}" });
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

            return Ok(new
            {
                message = "File uploaded successfully",
                type = uploadedFile.ContentType.StartsWith("video") ? "video" : "audio",
                backend = fileUrl
            });
        }

        [HttpPost("youtube")]
        public async Task<IActionResult> TranslateFromYoutube([FromBody] LinkRequest request)
        {
            try
            {
                var uploadsPath = Path.Combine(_env.ContentRootPath, "wwwroot", "uploads");
                Directory.CreateDirectory(uploadsPath);

                // Use a timestamp-based filename to avoid clashes
                var fileName = $"youtube_{DateTime.UtcNow.Ticks}.mp4";
                var filePath = Path.Combine(uploadsPath, fileName);

                // yt-dlp command
                var psi = new System.Diagnostics.ProcessStartInfo
                {
                    FileName = "yt-dlp",
                    Arguments = $"-f best -o \"{filePath}\" {request.Url}",
                    RedirectStandardError = true,
                    RedirectStandardOutput = true,
                    UseShellExecute = false
                };

                var process = System.Diagnostics.Process.Start(psi);
                if (process == null)
                    return StatusCode(500, "Failed to start yt-dlp process.");

                await process.WaitForExitAsync();

                if (process.ExitCode != 0)
                {
                    string error = await process.StandardError.ReadToEndAsync();
                    return StatusCode(500, $"yt-dlp failed: {error}");
                }

                var fileUrl = $"{Request.Scheme}://{Request.Host}/uploads/{fileName}";

                return Ok(new
                {
                    message = "YouTube video downloaded successfully",
                    type = "video",
                    backend = fileUrl
                });
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error downloading YouTube video: {ex.Message}");
            }
        }
    }

    public class LinkRequest
    {
        public string Url { get; set; } = string.Empty;
    }
}