import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { NavBarComponent } from '../nav-bar/nav-bar.component';
import { TranslateService } from '../services/translate.service';
import { FormsModule } from '@angular/forms';
import { MediaTransferService } from '../services/media-transfer.service';

@Component({
  selector: 'app-main-page',
  imports: [NavBarComponent, FormsModule],
  templateUrl: './main-page.component.html',
  styleUrl: './main-page.component.css'
})
export class MainPageComponent {
  mediaLink: string = '';

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

  /**
   * Navigate to the audio translation page.
   */
  goToAudioTranslationPage() {
    this.router.navigate(['/audio']);
  }

  /**
   * Navigate to the video translation page.
   */
  goToVideoTranslationPage() {
    this.router.navigate(['/video']);
  }

  OnMediaSelected(event: Event){
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      const file = input.files[0];
      console.log('Selected file:', file); // Can delete after, only testing purpose
      this.mediacontent.setFile(file);
      // Handle the selected media file (e.g., upload it)
      if (file.type.startsWith('video/')) {
      this.goToVideoTranslationPage();
    } else {
      this.goToAudioTranslationPage();
    }
  }
}
}
