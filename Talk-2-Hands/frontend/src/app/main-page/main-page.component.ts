import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { NavBarComponent } from '../nav-bar/nav-bar.component';
import { TranslateService } from '../services/translate.service';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common'; 
import { MediaTransferService } from '../services/media-transfer.service';
import { HttpEventType, HttpResponse } from '@angular/common/http';
import { timer, EMPTY, forkJoin } from 'rxjs';
import { switchMap, filter, takeUntil, take, map, catchError } from 'rxjs/operators';
import { ThemeService } from '../services/theme.service';
import { POPUP_ANIMATION } from '../models/constant';

@Component({
  selector: 'app-main-page',
  imports: [NavBarComponent, FormsModule, CommonModule],
  templateUrl: './main-page.component.html',
  styleUrl: './main-page.component.css',
  animations: [POPUP_ANIMATION] 
})
export class MainPageComponent {
  mediaLink: string = '';
  selectedFile: File | null = null;
  loading = false;
  isDarkMode = false;
  showPopup = false; 
  popupTitle = 'Missing Media';
  popupMessage = 'Please upload a file or paste a link before translating.';

  constructor(private translateService: TranslateService, private router: Router, private mediacontent: MediaTransferService, private theme: ThemeService) {}

  ngOnInit(): void {
    this.theme.isDarkMode$.subscribe(mode => this.isDarkMode = mode);
  }

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

  get isUploadDisabled(): boolean {
    return this.mediaLink.trim().length > 0;   // disable if link exists
  }

 translate() {
    // If a file was picked, upload to backend
    if (!this.selectedFile && !this.mediaLink.trim()) {
      this.showPopup = true;
      return;
    }
    if (this.selectedFile) {
      this.translateService.uploadFile(this.selectedFile).subscribe({
        next: (event: any) => {
          if (event.type === HttpEventType.UploadProgress) {
            const percent = Math.round(100 * event.loaded / event.total);
            console.log(`Upload progress: ${percent}%`);
          } else if (event instanceof HttpResponse) {
            // Final backend response
            console.log('Final backend response:', event.body);

            const res = event.body;
            const mediaData = {
              backend: res.backend,   // "/uploads/file.flac" for playback
              jobId: res.jobId,       // store this so you can poll status
              statusUrl: res.statusUrl,
              type: this.selectedFile!.type.startsWith('video/') ? 'video' : 'audio',
              fileName: this.selectedFile!.name
            };

            sessionStorage.setItem('media', JSON.stringify(mediaData));
            this.router.navigate(['/loading']);
          }
        },
        error: (err) => {
          console.error('Error uploading file:', err);
        }
      });
      return;
    }

    console.log('Before YouTube condition');
    if (this.mediaLink.trim()) {
      console.log('YouTube branch entered');
      try {
        console.log('Attempting to call sendYoutube...');
        this.translateService.sendYoutube(this.mediaLink.trim()).subscribe({
          next: (res: any) => {
            console.log('Backend YouTube response:', res);
            const mediaData = { ...res, type: 'video' };
            sessionStorage.setItem('media', JSON.stringify(mediaData));
            this.router.navigate(['/loading']);
          },
          error: (err) => console.error('Error sending YouTube link:', err)
        });
      } catch (err) {
        console.error('Error before subscribe:', err);
      }
      return;
    }
    // Nothing provided
    console.warn('Please paste a link or upload a file.');
  }

  onClosePopup() {
    this.showPopup = false;
  }
}

