import { Component, OnInit, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NavBarComponent } from '../nav-bar/nav-bar.component';
import { MediaTransferService } from '../services/media-transfer.service';
import { TranslateService } from '../services/translate.service';

@Component({
  selector: 'app-audio-translation-page',
  imports: [NavBarComponent, CommonModule],
  templateUrl: './audio-translation-page.component.html',
  styleUrl: './audio-translation-page.component.css'
})

export class AudioTranslationPageComponent implements OnInit{
  @ViewChild('audioPlayer', { static: false }) audioPlayer!: ElementRef<HTMLAudioElement>;
  @ViewChild('poseVideo', { static: false }) poseVideo!: ElementRef<HTMLVideoElement>;
  audioUrl: string | null = null;
  poseUrl: string | null = null;

  // Temporary display gloss
  gloss: string | null = null;
  jobId: string | null = null;
  fileName: string | null = null;
  private bound = false;

  constructor(private mediacontent: MediaTransferService, private translateService: TranslateService) { }
  // Injecting the MediaTransferService to access the selected media file

  ngOnInit(): void {
    console.log('[AudioTranslationPage] ngOnInit called');
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


  ngAfterViewChecked(): void {
    console.log('[AudioTranslationPage] ngAfterViewChecked called');
    console.log('  audioPlayer?', !!this.audioPlayer);
    console.log('  poseVideo?', !!this.poseVideo);
    if (!this.bound && this.audioPlayer && this.poseVideo) {
      const audio = this.audioPlayer.nativeElement;
      const video = this.poseVideo.nativeElement;

      console.log('[Sync] Binding audio <-> video events');
      this.bound = true;

      // Auto adjust playback speed to sync durations
      audio.addEventListener('loadedmetadata', () => {
        video.addEventListener('loadedmetadata', () => {
          if (video.duration && audio.duration) {
            const ratio = video.duration / audio.duration;
            video.playbackRate = ratio;
            console.log(`[Sync] Set playbackRate = ${ratio}`);
          }
        });
      });

      audio.addEventListener('play', () => video.play());
      audio.addEventListener('pause', () => video.pause());
      audio.addEventListener('ended', () => {
        video.pause();
        video.currentTime = 0;
      });
    }
  }

}
