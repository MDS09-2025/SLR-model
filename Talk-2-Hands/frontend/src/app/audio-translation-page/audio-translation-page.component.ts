import { Component, OnInit, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NavBarComponent } from '../nav-bar/nav-bar.component';
import { MediaTransferService } from '../services/media-transfer.service';
import { TranslateService } from '../services/translate.service';
import { ThemeService } from '../services/theme.service';
import { FormsModule } from '@angular/forms'; 
import { NgZone } from '@angular/core';

@Component({
  selector: 'app-audio-translation-page',
  imports: [NavBarComponent, CommonModule, FormsModule],
  templateUrl: './audio-translation-page.component.html',
  styleUrl: './audio-translation-page.component.css'
})

export class AudioTranslationPageComponent implements OnInit{
  @ViewChild('audioPlayer', { static: false }) audioPlayer!: ElementRef<HTMLAudioElement>;
  @ViewChild('poseVideo', { static: false }) poseVideo!: ElementRef<HTMLVideoElement>;
  @ViewChild('progressBar') progressBar!: ElementRef<HTMLInputElement>;
  audioUrl: string | null = null;
  poseUrl: string | null = null;

  // Temporary display gloss
  gloss: string | null = null;
  jobId: string | null = null;
  fileName: string | null = null;
  private bound = false;
  isDarkMode = false;
  isPlaying = false;
  currentTime = 0;
  duration = 0;
  private rafId: number | null = null;
  showSpeedMenu = false;
  playbackRate = 1.0;
  availableRates = [0.5, 1.0, 1.25, 1.5, 2.0];
  poseTiming: any[] = [];
  transcripts: string[] = [];
  currentSubtitle: string = '';

  constructor(private mediacontent: MediaTransferService, private translateService: TranslateService, private theme: ThemeService, private ngZone: NgZone) { }
  // Injecting the MediaTransferService to access the selected media file

  ngOnInit(): void {
    console.log('[AudioTranslationPage] ngOnInit called');
    this.theme.isDarkMode$.subscribe(mode => this.isDarkMode = mode);
    const stored = sessionStorage.getItem('media');
    console.log('[AudioTranslationPage] Stored media:', stored);
    if (stored) {
      const mediaData = JSON.parse(stored);
      console.log('[AudioTranslationPage] Parsed mediaData:', mediaData);
      if (mediaData.type === 'audio') {
        this.audioUrl = 'http://localhost:5027' + mediaData.backend;// Use the backend URL for audio
        console.log('Playing audio from backend:', this.audioUrl);
        this.gloss = mediaData.results?.gloss ?? null;
        this.jobId = mediaData.jobId;
        if (this.jobId) {
          // 🕒 Load pose_timing.json
          this.translateService.getPoseTiming(this.jobId).subscribe(data => {
            this.poseTiming = data;
            console.log('[Subtitles] Loaded pose_timing.json:', data);
          });

          // 💬 Load transcript text
          this.translateService.getTranscript(this.jobId).subscribe(text => {
            this.transcripts = text.split('\n').map(t => t.trim()).filter(Boolean);
            console.log('[Subtitles] Loaded transcript:', this.transcripts);
          });
        }
        this.translateService.getPoseVideo(this.jobId!).subscribe(blob => {
          this.poseUrl = URL.createObjectURL(blob);
          console.log('[AudioTranslationPage] Pose video URL:', this.poseUrl);
        });
        this.fileName = mediaData.backend.split('/').pop(); 
      } else {
        console.warn('Stored media is not audio');
      }
    } else {
      console.warn('No media found in session storage');
    }
  }

  downloadAudio() {
  if (this.jobId && this.fileName) {
    const baseName = this.fileName.replace(/\.[^/.]+$/, ''); // remove extension

    // 1️⃣ Download Audio
    this.translateService.downloadFile(this.jobId, this.fileName)
      .subscribe(audioBlob => {
        const audioUrl = window.URL.createObjectURL(audioBlob);
        const audioLink = document.createElement('a');
        audioLink.href = audioUrl;
        audioLink.download = `${baseName}_audio.wav`;
        document.body.appendChild(audioLink);
        audioLink.click();
        document.body.removeChild(audioLink);
        window.URL.revokeObjectURL(audioUrl);

        // 2️⃣ Then download Pose Video (avatar)
        this.translateService.getPoseVideo(this.jobId!).subscribe(videoBlob => {
          const videoUrl = window.URL.createObjectURL(videoBlob);
          const videoLink = document.createElement('a');
          videoLink.href = videoUrl;
          videoLink.download = `${baseName}_avatar.mp4`;
          document.body.appendChild(videoLink);
          videoLink.click();
          document.body.removeChild(videoLink);
          window.URL.revokeObjectURL(videoUrl);
        });
      });
  } else {
    console.warn('No audio/video available to download');
  }
}
  ngAfterViewChecked(): void {
  if (this.audioPlayer && !this.bound) {
    const audio = this.audioPlayer.nativeElement;
    this.bound = true;

    const updateProgress = () => {
      // runOutsideAngular to prevent triggering change detection too often
      this.ngZone.runOutsideAngular(() => {
        this.currentTime = audio.currentTime;

        // Only call detectChanges when necessary
        this.ngZone.run(() => {});
      });

      if (!audio.paused) {
        this.rafId = requestAnimationFrame(updateProgress);
      }
    };

    audio.addEventListener('play', () => {
      this.rafId = requestAnimationFrame(updateProgress);
    });

    audio.addEventListener('pause', () => {
      if (this.rafId) cancelAnimationFrame(this.rafId);
    });

    audio.addEventListener('ended', () => {
      if (this.rafId) cancelAnimationFrame(this.rafId);
      this.isPlaying = false;
      this.currentTime = 0;
    });

    audio.addEventListener('loadedmetadata', () => {
      this.duration = audio.duration;
    });
  }
}

togglePlay() {
  const audio = this.audioPlayer?.nativeElement;
  const video = this.poseVideo?.nativeElement;
  if (!audio) return;

  if (audio.paused) {
    audio.play();
    if (video) {
      video.currentTime = audio.currentTime; // keep synced
      video.play().catch(() => {
        console.warn('[PoseVideo] Autoplay blocked, waiting for user interaction.');
      });
    }
    this.isPlaying = true;
  } else {
    audio.pause();
    if (video) video.pause();
    this.isPlaying = false;
  }
}

seek(event: Event) {
  const audio = this.audioPlayer?.nativeElement;
  if (!audio) return;

  const value = parseFloat((event.target as HTMLInputElement).value);
  audio.currentTime = value;
  this.currentTime = value;
}

formatTime(time: number): string {
  if (!time || isNaN(time)) return '0:00';
  const minutes = Math.floor(time / 60);
  const seconds = Math.floor(time % 60);
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

ngAfterViewInit() {
  const audio = this.audioPlayer.nativeElement;
  const slider = this.progressBar.nativeElement;
  const video = this.poseVideo?.nativeElement;

  audio.addEventListener('loadedmetadata', () => {
    this.duration = audio.duration;
  });

  const update = () => {
    if (!audio.paused) {
      const percent = (audio.currentTime / audio.duration) * 100;
      slider.value = percent.toString();
      this.currentTime = audio.currentTime;

      // 🎨 Dynamic fill color
      // 🎨 improved dark/light contrast
      const playedColor = this.isDarkMode ? '#7B9FFF' : '#5371ff';   // brighter neon blue
      const remainingColor = this.isDarkMode ? '#2A2F38' : '#E5E7EB'; // darker background gray
      slider.style.background = `linear-gradient(to right, ${playedColor} ${percent}%, ${remainingColor} ${percent}%)`;

      // 🧩 Keep video synced
      if (video && Math.abs(video.currentTime - audio.currentTime) > 0.1) {
        video.currentTime = audio.currentTime;
      }

      requestAnimationFrame(update);
    }
  };

  audio.addEventListener('play', () => {
    this.isPlaying = true;
    requestAnimationFrame(update);
  });

  audio.addEventListener('pause', () => {
    this.isPlaying = false;
  });

  slider.addEventListener('input', () => {
    const seekTime = (parseFloat(slider.value) / 100) * audio.duration;
    audio.currentTime = seekTime;
    this.currentTime = seekTime;
  });

  if (video) {
    video.addEventListener('timeupdate', () => {
      const time = video.currentTime;
      const seg = this.poseTiming.find(s => time >= s.start && time < s.end);
      if (seg) {
        const idx = this.poseTiming.indexOf(seg);
        const newSubtitle = this.transcripts[idx] || '';
        if (this.currentSubtitle !== newSubtitle) {
          this.currentSubtitle = newSubtitle;
        }
      } else {
        this.currentSubtitle = '';
      }
    });
  }
}

rewind(seconds: number = 1) {
  const audio = this.audioPlayer?.nativeElement;
  const video = this.poseVideo?.nativeElement;
  if (!audio) return;

  audio.currentTime = Math.max(audio.currentTime - seconds, 0);
  this.currentTime = audio.currentTime;

  if (video) {
    video.currentTime = audio.currentTime; // stay synced
  }
}

forward(seconds: number = 1) {
  const audio = this.audioPlayer?.nativeElement;
  const video = this.poseVideo?.nativeElement;
  if (!audio) return;

  audio.currentTime = Math.min(audio.currentTime + seconds, audio.duration);
  this.currentTime = audio.currentTime;

  if (video) {
    video.currentTime = audio.currentTime; // stay synced
  }
}

toggleSpeedMenu() {
  this.showSpeedMenu = !this.showSpeedMenu;
}


setPlaybackRate(rate: number) {
  const audio = this.audioPlayer?.nativeElement;
  const video = this.poseVideo?.nativeElement;
  this.playbackRate = rate;

  if (audio) audio.playbackRate = rate;
  if (video) video.playbackRate = rate;
  this.showSpeedMenu = false;
}
}
