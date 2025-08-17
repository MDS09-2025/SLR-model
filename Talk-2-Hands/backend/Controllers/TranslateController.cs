using Microsoft.AspNetCore.Mvc;

namespace Talk2Hands.Backend.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class TranslateController : ControllerBase
    {
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

            return Ok(new { message = $"Got file: {uploadedFile.FileName}" });
        }
    }

    public class LinkRequest
    {
        public string Url { get; set; }
    }
}