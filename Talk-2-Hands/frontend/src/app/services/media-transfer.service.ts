import { Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root'
})

export class MediaTransferService {
  private file: File | null = null;
  private link: string | null = null;

  setFile(file: File | null) {
    this.file = file;
  }

  getFile(): File | null {
    return this.file;
  }

  clearFile() {
    this.file = null;
  }

  setLink(url: string | null) { 
    this.link = url; 
  }

  getLink() { 
    return this.link; 
  }
}