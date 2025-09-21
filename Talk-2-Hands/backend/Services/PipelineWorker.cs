// Services/PipelineWorker.cs
using System.Diagnostics;
using Talk2Hands.Backend.Models;

namespace Talk2Hands.Backend.Services;
public class PipelineWorker : BackgroundService {
    private readonly IPipelineQueue _queue;
    private readonly IPipelineStore _store;
    private readonly IWebHostEnvironment _env;
    private readonly ILogger<PipelineWorker> _log;
    private readonly IConfiguration _cfg;

    public PipelineWorker(IPipelineQueue q, IPipelineStore s, IWebHostEnvironment env, IConfiguration cfg, ILogger<PipelineWorker> log) {
        _queue = q; _store = s; _env = env; _cfg = cfg; _log = log;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken) {
        await foreach (var job in _queue.DequeueAllAsync(stoppingToken)) {
            try {
                job.Status = JobState.Running; Save(job);

                var raw      = Path.Combine(job.WorkDir, "Raw_Audio");
                var clean    = Path.Combine(job.WorkDir, "Clean_Audio");
                var transDir = Path.Combine(job.WorkDir, "Transcripts");
                Directory.CreateDirectory(raw);
                Directory.CreateDirectory(clean);
                Directory.CreateDirectory(transDir);

                var python = _cfg["Pipeline:PythonPath"] ?? "python3";
                Console.WriteLine($"[DEBUG] Running python: {python}");

                var scriptSetting = _cfg["Pipeline:ScriptPath"] ?? "python/audio_text_gloss.py";
                var script = Path.IsPathRooted(scriptSetting)
                    ? scriptSetting
                    : Path.Combine(_env.ContentRootPath, scriptSetting);

                if (!System.IO.File.Exists(script))
                    throw new FileNotFoundException($"Pipeline script not found: {script}");

                // 1) preprocess
                job.Steps.Add("preprocess"); Save(job);
                await RunPython(python, script, job.WorkDir,
                    "--preprocess",
                    "--raw_dir", raw, "--clean_dir", clean,
                    "--target_sr","48000", "--chunk_sec","10.0",
                    "--transcript_txt", Path.Combine(job.WorkDir, "transcription_output.txt"),
                    "--gloss_txt",      Path.Combine(job.WorkDir, "gloss_output.txt")
                );

                // 2) transcribe
                job.Steps.Add("transcribe"); Save(job);
                await RunPython(python, script, job.WorkDir,
                    "--transcribe",
                    "--clean_dir", clean,
                    "--whisper_size", _cfg["Pipeline:WhisperSize"] ?? "large-v3",
                    "--asr_device",    _cfg["Pipeline:AsrDevice"]   ?? "cpu",
                    "--compute_type",  _cfg["Pipeline:ComputeType"] ?? "float32",
                    "--beam_size",     _cfg["Pipeline:BeamSize"]    ?? "5"
                );

                // 3) translate
                job.Steps.Add("translate"); Save(job);
                // var modelPath  = ResolvePath(_cfg["Pipeline:T2GModel"]  ?? "../../transformer_model.pt");
                // Console.WriteLine($"[DEBUG] _cfg[T2GModel]: {_cfg["Pipeline:T2GModel"]}");
                // var configPath = ResolvePath(_cfg["Pipeline:T2GConfig"] ?? "../../transformer_model_config.json");
                // var vocabPath  = ResolvePath(_cfg["Pipeline:T2GVocab"]  ?? "../../transformer_vocab.json");

                // if (!File.Exists(modelPath))  throw new FileNotFoundException($"Missing T2G model at {modelPath}");
                // if (!File.Exists(configPath)) throw new FileNotFoundException($"Missing T2G config at {configPath}");
                // if (!File.Exists(vocabPath))  throw new FileNotFoundException($"Missing T2G vocab at {vocabPath}");

                // await RunPython(python, script, job.WorkDir,
                //     "--translate",
                //     "--t2g_model",  modelPath,
                //     "--t2g_config", configPath,
                //     "--t2g_vocab",  vocabPath,
                //     "--max_src_len","64","--max_len","100",
                //     "--t2g_decoder","beam","--t2g_beam","8","--t2g_lenpen","0.7",
                //     "--transcript_txt", Path.Combine(job.WorkDir, "transcription_output.txt"),
                //     "--gloss_txt",      Path.Combine(job.WorkDir, "gloss_output.txt"),
                //     "--t2g_cpu"
                // );

                var modelPath = _cfg["Pipeline:T2GModel"] ?? "../../t5-finetuned-aslg";

                if (!Directory.Exists(modelPath))
                    throw new DirectoryNotFoundException($"T2G model directory not found: {modelPath}");

                await RunPython(python, script, job.WorkDir,
                    "--translate",
                    "--t2g_model", modelPath,   
                    "--max_src_len","64","--max_len","100",
                    "--t2g_decoder","beam","--t2g_beam","8","--t2g_lenpen","0.7",
                    "--transcript_txt", Path.Combine(job.WorkDir, "transcription_output.txt"),
                    "--gloss_txt",      Path.Combine(job.WorkDir, "gloss_output.txt"),
                    "--t2g_cpu",
                    "--render_pose",
                    "--pose_dir", Path.Combine(job.WorkDir, "Pose_Output"),
                    "--gloss2pose_dir", _cfg["Pipeline:Gloss2PoseDir"],
                    "--job_id", job.JobId 
                );


                job.Status = JobState.Finished;
                job.Results["transcript"] = $"{job.PublicBase}/transcription_output.txt";
                job.Results["gloss"]      = $"{job.PublicBase}/gloss_output.txt";
                job.Results["poses"]      = $"{job.PublicBase}/Pose_Output";
                Save(job);
            }
            catch (Exception ex) {
                job.Status = JobState.Failed;
                job.Error = ex.ToString();
                Save(job);
            }
        }
    }

    private void Save(PipelineJob j) => _store.All[j.JobId] = j;
    
    private string ResolvePath(string p) =>
        Path.IsPathRooted(p) ? p : Path.GetFullPath(Path.Combine(_env.ContentRootPath, p));

    private static async Task RunPython(string python, string script, string workdir, params string[] args) {
        var psi = new ProcessStartInfo {
            FileName = python,
            WorkingDirectory = workdir,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false
        };
        psi.ArgumentList.Add(script);
        foreach (var a in args) psi.ArgumentList.Add(a);

        using var p = Process.Start(psi)!;

        var logFile = Path.Combine(workdir, "pipeline.log");
        await using var log = new StreamWriter(logFile, append: true);

        _ = Task.Run(async () => {
            while (!p.StandardOutput.EndOfStream) {
                var line = await p.StandardOutput.ReadLineAsync();
                Console.WriteLine(line);
                await log.WriteLineAsync(line);
            }
        });
        _ = Task.Run(async () => {
            while (!p.StandardError.EndOfStream) {
                var line = await p.StandardError.ReadLineAsync();
                Console.WriteLine(line);
                await log.WriteLineAsync("ERR: " + line);
            }
        });

        await p.WaitForExitAsync();
        if (p.ExitCode != 0)
            throw new Exception($"python exited {p.ExitCode}");
    }

}
