import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NavBarComponent } from '../nav-bar/nav-bar.component';
import { MediaTransferService } from '../services/media-transfer.service';

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

  constructor(private mediacontent: MediaTransferService) { }
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
      } else {
        console.warn('Stored media is not audio');
      }
    } else {
      console.warn('No media found in session storage');
    }
    // const file = this.mediacontent.getFile();
    // if (file) {
    //   console.log('Selected file in AudioTranslationPage:', file);
    //   this.audioUrl = URL.createObjectURL(file);
    //   // Create a URL for the audio file to be played
    // }
  }

}
