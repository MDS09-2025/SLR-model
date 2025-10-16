using Microsoft.AspNetCore.Mvc;
using System.Text.RegularExpressions;
using System.Diagnostics;
using Talk2Hands.Backend.Models;
using Talk2Hands.Backend.Services;


namespace Talk2Hands.Backend.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class TranslateController : ControllerBase
    {
        private readonly IWebHostEnvironment _env;
        private readonly IPipelineStore _store;
        private readonly IPipelineQueue _queue;
        private readonly IConfiguration _cfg;

        public TranslateController(IWebHostEnvironment env, IPipelineStore store, IPipelineQueue queue, IConfiguration cfg)
        {
            _env = env; _store = store; _queue = queue; _cfg = cfg;
        }

        // POST /api/translate/upload
        [HttpPost("upload")]
        [RequestSizeLimit(long.MaxValue)]
        public async Task<IActionResult> Upload([FromForm] IFormFile uploadedFile)
        {
            if (uploadedFile is null || uploadedFile.Length == 0)
                return BadRequest("No file uploaded.");

            var webRoot = _env.WebRootPath ?? Path.Combine(_env.ContentRootPath, "wwwroot");
            var jobsRoot = Path.Combine(webRoot, "jobs");
            Directory.CreateDirectory(jobsRoot);

            var jobId = Guid.NewGuid().ToString("N");
            var jobWork = Path.Combine(jobsRoot, jobId);
            Directory.CreateDirectory(jobWork);

            var safeName = Path.GetFileName(uploadedFile.FileName);
            var originalPath = Path.Combine(jobWork, safeName);

            // 2) Save original upload into job folder
            await using (var fs = System.IO.File.Create(originalPath))
                await uploadedFile.CopyToAsync(fs);

            // 3) Prepare Raw_Audio folder
            var rawDir = Path.Combine(jobWork, "Raw_Audio");
            Directory.CreateDirectory(rawDir);

            var ext = Path.GetExtension(safeName).ToLowerInvariant();
            var isVideo = Regex.IsMatch(ext, @"\.(mp4|mov|mkv|avi|webm)$");
            if (isVideo)
            {
                var wavOut = Path.Combine(rawDir, Path.GetFileNameWithoutExtension(safeName) + ".wav");
                await RunFfmpeg(originalPath, wavOut);
            }
            else
            {
                // System.IO.File.Copy(publicDiskPath, Path.Combine(rawDir, safeName), overwrite: true);
                System.IO.File.Copy(originalPath, Path.Combine(rawDir, safeName), overwrite: true);
            }

            // 4) Register + enqueue job
            var job = new PipelineJob
            {
                JobId = jobId,               
                SourceType = "upload",
                WorkDir = jobWork,
                PublicBase = $"/jobs/{jobId}"
            };
            _store.Add(job);
            await _queue.EnqueueAsync(job);

            // 5) IMPORTANT: match your Angular expectation → res.backend is a URL
            //    You store { backend: res, type, fileName } so res must have "backend" string
            if (isVideo)
            {
                // for video uploads: backend points to the original video
                return Ok(new
                {
                    backend = $"{job.PublicBase}/{job.JobId}.mp4",
                    jobId = job.JobId,
                    statusUrl = $"/api/translate/status/{job.JobId}"
                });
            }
            else
            {
                // for audio uploads: backend points to the padded audio (produced later by pipeline)
                return Ok(new
                {
                    backend = $"{job.PublicBase}/{job.JobId}.wav",
                    jobId = job.JobId,
                    statusUrl = $"/api/translate/status/{job.JobId}"
                });
            }
        }

        public sealed record YoutubeReq(string Url);

        [HttpPost("youtube")]
        public async Task<IActionResult> Youtube([FromBody] YoutubeReq body)
        {
            Console.WriteLine(">>> [YouTube API] Endpoint hit");
            if (string.IsNullOrWhiteSpace(body?.Url))
                return BadRequest("Missing url");

            Console.WriteLine($">>> [YouTube API] Received URL: {body.Url}");
            var webRoot = _env.WebRootPath ?? Path.Combine(_env.ContentRootPath, "wwwroot");
            var jobsRoot = Path.Combine(webRoot, "jobs");
            Directory.CreateDirectory(jobsRoot);
            
            var jobId = Guid.NewGuid().ToString("N");
            var jobWork = Path.Combine(jobsRoot, jobId);
            Directory.CreateDirectory(jobWork);
            
            Console.WriteLine($">>> [YouTube API] Job folder created: {jobWork}");

            // Step 1: pick a predictable safe filename
            var safeName = $"youtube_{DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()}.mp4";
            var videoPath = Path.Combine(jobWork, safeName);

            var job = new PipelineJob
            {
                JobId = jobId,
                SourceType = "youtube",
                WorkDir = jobWork,
                PublicBase = $"/jobs/{jobId}",
                Status = JobState.Queued
            };
            
            _store.Add(job);

            _ = Task.Run(async () =>
            {
                try
                {
                    job.Status = JobState.Running;
                    Console.WriteLine($">>> [YouTube API] [Job:{jobId}] Starting yt-dlp...");

                    var psi = new ProcessStartInfo
                    {
                        FileName = "yt-dlp",
                        ArgumentList = {
                            "--no-playlist",
                            "-f", "best[height<=720]",
                            "--merge-output-format", "mp4",
                            "-o", videoPath,
                            body.Url
                        },
                        RedirectStandardError = true,
                        RedirectStandardOutput = true,
                        UseShellExecute = false
                    };

                    using var proc = Process.Start(psi)!;
                    string stderr = await proc.StandardError.ReadToEndAsync();
                    string stdout = await proc.StandardOutput.ReadToEndAsync();
                    await proc.WaitForExitAsync();

                    if (proc.ExitCode != 0 || !System.IO.File.Exists(videoPath))
                    {
                        Console.WriteLine($">>> [YouTube API] [Job:{jobId}] yt-dlp failed: {stderr}");
                        job.Status = JobState.Failed;
                        job.Error = "YouTube download failed.";
                        return;
                    }

                    Console.WriteLine($">>> [YouTube API] [Job:{jobId}] Download complete: {videoPath}");

                    var rawDir = Path.Combine(jobWork, "Raw_Audio");
                    Directory.CreateDirectory(rawDir);
                    var wavOut = Path.Combine(rawDir, Path.GetFileNameWithoutExtension(safeName) + ".wav");

                    await RunFfmpeg(videoPath, wavOut);
                    Console.WriteLine($">>> [YouTube API] [Job:{jobId}] Extracted audio successfully");

                    await _queue.EnqueueAsync(job);
                    Console.WriteLine($">>> [YouTube API] [Job:{jobId}] Job enqueued successfully");
                }
                 catch (Exception ex)
                {
                    job.Status = JobState.Failed;
                    job.Error = ex.Message;
                    Console.WriteLine($">>> [YouTube API] [Job:{jobId}] Exception: {ex}");
                }
            });

            // ✅ Return immediately with job details (frontend can start polling)
            var response = new
            {
                type = "video",
                backend = $"{job.PublicBase}/{job.JobId}.mp4",
                jobId = job.JobId,
                statusUrl = $"/api/translate/status/{job.JobId}"
            };

            Console.WriteLine($">>> [YouTube API] Returning immediate response for job {jobId}");
            return Ok(response);
        }

        // GET /api/translate/status/{jobId}
        [HttpGet("status/{jobId}")]
        public IActionResult Status(string jobId) =>
            _store.TryGet(jobId, out var job) ? Ok(job) : NotFound();

        // GET /api/translate/result/{jobId}/{which}
        [HttpGet("result/{jobId}/{which}")]
        public IActionResult Result(string jobId, string which)
        {
            if (!_store.TryGet(jobId, out var job)) return NotFound();

            var file = which.ToLower() switch
            {
                "transcript" => Path.Combine(job.WorkDir, "transcription_output.txt"),
                "gloss" => Path.Combine(job.WorkDir, "gloss_output.txt"),
                "poses"      => Path.Combine(job.WorkDir, "Pose_Output"),
                _ => null
            };
            if (file is null || !System.IO.File.Exists(file)) return NotFound("Not ready");

            return PhysicalFile(file, "text/plain", Path.GetFileName(file));
        }

        private static async Task RunFfmpeg(string input, string output)
        {
            var psi = new System.Diagnostics.ProcessStartInfo
            {
                FileName = "ffmpeg",
                ArgumentList = { "-y", "-i", input, "-vn", "-ac", "1", "-ar", "48000", output },
                RedirectStandardError = true,
                RedirectStandardOutput = true,
                UseShellExecute = false
            };
            using var p = System.Diagnostics.Process.Start(psi)!;
            var stderr = await p.StandardError.ReadToEndAsync();
            await p.WaitForExitAsync();
            if (p.ExitCode != 0)
                throw new Exception($"ffmpeg failed: {stderr}");
        }

        [HttpGet("download/{jobId}/{fileName}")]
        public IActionResult Download(string jobId, string fileName)
        {
            var webRoot = _env.WebRootPath ?? Path.Combine(_env.ContentRootPath, "wwwroot");
            var jobsRoot = Path.Combine(webRoot, "jobs");
            var jobPath = Path.Combine(jobsRoot, jobId);
            var filePath = Path.Combine(jobPath, fileName);

            if (!System.IO.File.Exists(filePath))
                return NotFound();

            // Default MIME type
            var mimeType = "application/octet-stream";

            // Audio types
            if (fileName.EndsWith(".mp3", StringComparison.OrdinalIgnoreCase))
                mimeType = "audio/mpeg";
            else if (fileName.EndsWith(".wav", StringComparison.OrdinalIgnoreCase))
                mimeType = "audio/wav";
            else if (fileName.EndsWith(".flac", StringComparison.OrdinalIgnoreCase))
                mimeType = "audio/flac";
            else if (fileName.EndsWith(".mp4", StringComparison.OrdinalIgnoreCase))
                mimeType = "video/mp4";

            // Video types
            else if (fileName.EndsWith(".mp4", StringComparison.OrdinalIgnoreCase))
                mimeType = "video/mp4";
            else if (fileName.EndsWith(".mov", StringComparison.OrdinalIgnoreCase))
                mimeType = "video/quicktime";
            else if (fileName.EndsWith(".avi", StringComparison.OrdinalIgnoreCase))
                mimeType = "video/x-msvideo";
            else if (fileName.EndsWith(".mkv", StringComparison.OrdinalIgnoreCase))
                mimeType = "video/x-matroska";
            else if (fileName.EndsWith(".webm", StringComparison.OrdinalIgnoreCase))
                mimeType = "video/webm";

            // 👇 Always force download
            return PhysicalFile(filePath, mimeType, fileName);
        }
    }
}