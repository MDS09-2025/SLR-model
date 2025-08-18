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

  @ViewChild('player') playerRef?: ElementRef<HTMLVideoElement>;  // ✅ reference to <video>
  
  constructor(private mediaService: MediaTransferService){}

  // ngOnInit(): void {
  //   const file = this.mediaService.getFile();
  //   const link = this.mediaService.getLink();

  //   // If video file is uploaded
  //   if (file) {
  //     this.localFile = file;
  //     console.log('Playing video file:', file);
  //     this.videoSrc = URL.createObjectURL(file);
  //   } else if (link) {
  //     console.log('Playing video link:', link);
  //     this.videoSrc = link;
  //   }
  // }
  ngOnInit(): void {
    console.log('[VideoTranslationPage] ngOnInit called');
    const stored = sessionStorage.getItem('media');
    console.log('[VideoTranslationPage] Stored media:', stored);

    if (stored) {
      const mediaData = JSON.parse(stored);
      console.log('[VideoTranslationPage] Parsed mediaData:', mediaData);

      if (mediaData.type === 'video') {
        // backend object might be nested (backend.backend) or direct string
        this.videoSrc = mediaData.backend;
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