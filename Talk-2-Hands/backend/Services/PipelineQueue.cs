using System.Threading.Channels;
using System.Runtime.CompilerServices; // <-- needed for [EnumeratorCancellation]
using Talk2Hands.Backend.Models;

namespace Talk2Hands.Backend.Services;
public interface IPipelineQueue
{
    ValueTask EnqueueAsync(PipelineJob job);
    IAsyncEnumerable<PipelineJob> DequeueAllAsync(CancellationToken ct);
}
public class PipelineQueue : IPipelineQueue {
    private readonly Channel<PipelineJob> _ch = Channel.CreateUnbounded<PipelineJob>();
    public ValueTask EnqueueAsync(PipelineJob job) => _ch.Writer.WriteAsync(job);
    public async IAsyncEnumerable<PipelineJob> DequeueAllAsync([EnumeratorCancellation] CancellationToken ct) {
        while (await _ch.Reader.WaitToReadAsync(ct))
            while (_ch.Reader.TryRead(out var job)) yield return job;
    }
}