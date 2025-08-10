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
        public IActionResult TranslateFromUpload(IFormFile file) 
        {
            if (file == null || file.Length == 0)
                return BadRequest("No file uploaded.");

            return Ok(new { message = $"Got file: {file.FileName}"});
        }
    }

    public class LinkRequest
    {
        public string Url { get; set; }
    }
}