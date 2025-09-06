import { Component, ElementRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NavBarComponent } from '../nav-bar/nav-bar.component';
import { MediaTransferService } from '../services/media-transfer.service';
import { TranslateService } from '../services/translate.service';

@Component({
  selector: 'app-video-translation-page',
  standalone: true,
  imports: [CommonModule, NavBarComponent],
  templateUrl: './video-translation-page.component.html'
})
export class VideoTranslationPageComponent {
  videoSrc: string | null = null;
  localFile?: File;
  // Temporary display gloss
  gloss: string | null = null;
  jobId: string | null = null;
  fileName: string | null = null;


  @ViewChild('player') playerRef?: ElementRef<HTMLVideoElement>;  // ✅ reference to <video>
  
  constructor(private mediaService: MediaTransferService, private translateService: TranslateService){}

  ngOnInit(): void {
    console.log('[VideoTranslationPage] ngOnInit called');
    const stored = sessionStorage.getItem('media');
    console.log('[VideoTranslationPage] Stored media:', stored);

    if (stored) {
      const mediaData = JSON.parse(stored);
      console.log('[VideoTranslationPage] Parsed mediaData:', mediaData);

      if (mediaData.type === 'video') {
        this.videoSrc = `http://localhost:5027${mediaData.backend}`;
        this.gloss = mediaData.results?.gloss ?? null;
        console.log('Playing video from backend:', this.videoSrc);
        this.jobId = mediaData.jobId;
        this.fileName = mediaData.backend.split('/').pop(); 
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