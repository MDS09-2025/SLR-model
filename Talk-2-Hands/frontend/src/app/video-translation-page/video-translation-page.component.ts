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

  ngOnInit(): void {
    const file = this.mediaService.getFile();
    const link = this.mediaService.getLink();

    // If video file is uploaded
    if (file) {
      this.localFile = file;
      console.log('Playing video file:', file);
      this.videoSrc = URL.createObjectURL(file);
    } else if (link) {
      console.log('Playing video link:', link);
      this.videoSrc = link;
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