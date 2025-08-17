import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { NavBarComponent } from '../nav-bar/nav-bar.component';
import { TranslateService } from '../services/translate.service';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common'; 
import { MediaTransferService } from '../services/media-transfer.service';

@Component({
  selector: 'app-main-page',
  imports: [NavBarComponent, FormsModule, CommonModule],
  templateUrl: './main-page.component.html',
  styleUrl: './main-page.component.css'
})
export class MainPageComponent {
  mediaLink: string = '';
  selectedFile: File | null = null;

  constructor(private translateService: TranslateService, private router: Router, private mediacontent: MediaTransferService) {}

  sendLink() {
    this.translateService.sendLink(this.mediaLink).subscribe({
      next: (res) => {
        console.log('Backend response:', res);
        this.mediaLink = ''; // Clear the input field after sending
      },
      error: (err) => console.error('Error sending link:', err)
    });
  }

  onFilePicked(event: Event){
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('audio/') && !file.type.startsWith('video/')) {
      console.error('Unsupported type'); // replace with your toast
      return;
    }
    this.selectedFile = file;
    this.mediacontent.setFile(file);
    this.mediacontent.setLink(null); // prefer file if both present
  }

  translate() {
    // If a file was picked, it takes precedence
    if (this.selectedFile) {
      const isVideo = this.selectedFile.type.startsWith('video/');
      const route = isVideo ? '/video' : '/audio';
      this.router.navigate([route]);
      return;
    }

    // Else, if a link is provided, treat as video (YouTube link)
    if (this.mediaLink.trim()) {
      this.mediacontent.setLink(this.mediaLink.trim());
      this.mediacontent.setFile(null);
      // (Optional) validate YouTube URL
      // if (!this.isYouTube(this.mediaLink.trim())) { ... show error ...; return; }
      this.router.navigate(['/video']);
      return;
    }

    // Nothing provided
    console.warn('Please paste a link or upload a file.');
  }
}

