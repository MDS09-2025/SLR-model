// Models/PipelineJob.cs
namespace Talk2Hands.Backend.Models;

public enum JobState { Queued, Running, Finished, Failed }

public sealed class PipelineJob {
    public string JobId { get; init; } = Guid.NewGuid().ToString("N");
    public JobState Status { get; set; } = JobState.Queued;
    public string SourceType { get; set; } = ""; // "upload" | "youtube"
    public List<string> Steps { get; } = new();
    public string? Error { get; set; }
    public string WorkDir { get; init; } = "";       // physical path: wwwroot/jobs/{jobId}
    public string PublicBase { get; init; } = "";    // public base: /jobs/{jobId}
    public Dictionary<string,string?> Results { get; } = new()
    {
        ["transcript"] = null,
        ["gloss"] = null,
        ["poses"] = null
    };
}
