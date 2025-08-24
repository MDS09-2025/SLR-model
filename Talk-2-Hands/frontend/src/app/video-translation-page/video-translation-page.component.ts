import { Component, ElementRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NavBarComponent } from '../nav-bar/nav-bar.component';
import { MediaTransferService } from '../services/media-transfer.service';

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

  @ViewChild('player') playerRef?: ElementRef<HTMLVideoElement>;  // ✅ reference to <video>
  
  constructor(private mediaService: MediaTransferService){}

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

  download() {
    if (this.localFile) {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(this.localFile);
      a.download = this.localFile.name;
      a.click();
      return;
    }
   
    if (this.videoSrc) window.open(this.videoSrc, '_blank');
  }
}