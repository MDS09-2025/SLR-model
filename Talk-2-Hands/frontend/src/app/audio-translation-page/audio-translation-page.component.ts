import { Component, OnInit } from '@angular/core';
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
  audioUrl: string | null = null;
  // This will hold the URL of the audio file to be played

  // Temporary display gloss
  gloss: string | null = null;
  jobId: string | null = null;
  fileName: string | null = null;

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
}
