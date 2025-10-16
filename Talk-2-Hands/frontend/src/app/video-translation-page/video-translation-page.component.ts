import { Component, ElementRef, ViewChild, NgZone, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NavBarComponent } from '../nav-bar/nav-bar.component';
import { MediaTransferService } from '../services/media-transfer.service';
import { TranslateService } from '../services/translate.service';
import { ThemeService } from '../services/theme.service';

@Component({
  selector: 'app-video-translation-page',
  standalone: true,
  imports: [CommonModule, NavBarComponent],
  templateUrl: './video-translation-page.component.html'
})
export class VideoTranslationPageComponent implements OnInit {
  videoSrc: string | null = null;
  localFile?: File;
  // Temporary display gloss
  gloss: string | null = null;
  jobId: string | null = null;
  fileName: string | null = null;
  isDarkMode = false;
  poseTiming: any[] = [];
  transcripts: string[] = [];
  currentSubtitle: string = '';


  @ViewChild('player') playerRef?: ElementRef<HTMLVideoElement>;  // ✅ reference to <video>
  
  constructor(private mediaService: MediaTransferService, private translateService: TranslateService, private theme: ThemeService, private ngZone: NgZone){}

  ngOnInit(): void {
    console.log('[VideoTranslationPage] ngOnInit called');
    this.theme.isDarkMode$.subscribe(mode => this.isDarkMode = mode);
    
    const stored = sessionStorage.getItem('media');
    console.log('[VideoTranslationPage] Stored media:', stored);

    if (stored) {
      const mediaData = JSON.parse(stored);
      console.log('[VideoTranslationPage] Parsed mediaData:', mediaData);

      if (mediaData.type === 'video') {
        this.videoSrc = `http://localhost:5027${mediaData.backend}`;
        this.gloss = mediaData.results?.gloss ?? null;
        console.log('Playing video from backend:', this.videoSrc);
        setTimeout(() => {
          const video = this.playerRef?.nativeElement;
          if (video) {
            video.load();  // force reload source
          }
        }, 1000);
        this.jobId = mediaData.jobId;
        this.fileName = mediaData.backend.split('/').pop(); 
        if (this.jobId) {
          this.translateService.getPoseTiming(this.jobId).subscribe(data => {
            this.poseTiming = data;
            console.log('[Subtitles] Loaded pose_timing.json:', data);
          });

          this.translateService.getTranscript(this.jobId).subscribe(text => {
            this.transcripts = text.split('\n').map(t => t.trim()).filter(Boolean);
            console.log('[Subtitles] Loaded transcript:', this.transcripts);
          });

          // 🧠 Bind timeupdate after video loads
          setTimeout(() => {
            const video = this.playerRef?.nativeElement;
            if (!video) return;
            console.log('[SubtitleSync] Binding after video loaded');

            video.addEventListener('timeupdate', () => {
              const time = video.currentTime;
              if (!this.poseTiming?.length || !this.transcripts?.length) return;

              const seg = this.poseTiming.find(s => time + 0.1 >= s.start && time <= s.end + 0.1);
              this.ngZone.run(() => {
                  this.currentSubtitle = seg
                    ? this.transcripts[this.poseTiming.indexOf(seg)] || ''
                    : '';
                });
              if (this.currentSubtitle)
                  console.log('[Subtitle]', this.currentSubtitle);
            });
          }, 500);
        }
      } else {
        console.warn('Stored media is not video');
      }
    } else {
      console.warn('No media found in session storage');
    }
  }

  toggleFullScreen() {
    const videoEl = this.playerRef?.nativeElement;
    if (!videoEl) return;

    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      videoEl.requestFullscreen();  // ✅ fullscreen on actual video
    }
  }

  downloadVideo() {
    if (this.jobId && this.fileName) {
      this.translateService.downloadFile(this.jobId, this.fileName)
        .subscribe(blob => {
          // create download link from blob
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = this.fileName!; // keep original name
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          window.URL.revokeObjectURL(url); // cleanup
        });
    } else {
      console.warn('No audio/video available to download');
    }
  }

}