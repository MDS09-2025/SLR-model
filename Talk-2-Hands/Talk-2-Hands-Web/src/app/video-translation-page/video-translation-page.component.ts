import { Component, ElementRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NavBarComponent } from '../nav-bar/nav-bar.component';

@Component({
  selector: 'app-video-translation-page',
  standalone: true,
  imports: [CommonModule, NavBarComponent],
  templateUrl: './video-translation-page.component.html'
})
export class VideoTranslationPageComponent {

  videoSrc: string | null = '/assets/sample/sample.mp4';
  localFile?: File;
  status = '';

  @ViewChild('videoCard') cardRef?: ElementRef<HTMLDivElement>;

  onFile(e: Event) {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;
    this.localFile = file;
    this.videoSrc = URL.createObjectURL(file);
    this.status = '${file.name}';
  }

  toggleFullScreen() {
    const el = this.cardRef?.nativeElement ?? document.documentElement;
    if (document.fullscreenElement) document.exitFullscreen();
    else el.requestFullscreen();
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