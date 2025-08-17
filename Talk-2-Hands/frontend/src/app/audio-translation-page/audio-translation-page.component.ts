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

  constructor(private mediacontent: MediaTransferService) { }
  // Injecting the MediaTransferService to access the selected media file

  ngOnInit(): void {
    const file = this.mediacontent.getFile();
    if (file) {
      console.log('Selected file in AudioTranslationPage:', file);
      this.audioUrl = URL.createObjectURL(file);
      // Create a URL for the audio file to be played
    }
  }

}
