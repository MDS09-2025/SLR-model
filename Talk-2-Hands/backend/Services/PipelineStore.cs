using System.Collections.Concurrent;
using Talk2Hands.Backend.Models;

namespace Talk2Hands.Backend.Services;
public interface IPipelineStore
{
    PipelineJob Add(PipelineJob job);
    bool TryGet(string id, out PipelineJob? job);
    ConcurrentDictionary<string, PipelineJob> All { get; }
}
public class PipelineStore : IPipelineStore {
    public ConcurrentDictionary<string, PipelineJob> All { get; } = new();
    public PipelineJob Add(PipelineJob job) { All[job.JobId] = job; return job; }
    public bool TryGet(string id, out PipelineJob? job) => All.TryGetValue(id, out job);
}