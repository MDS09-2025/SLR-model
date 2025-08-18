import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class TranslateService {
  private apiUrl = 'http://localhost:5027/api/translate'; // match backend URL

  constructor(private http: HttpClient) {}

  sendLink(url: string) {
    return this.http.post(`${this.apiUrl}/link`, { url });
  }

  uploadFile(file: File) {
    console.log('[TranslateService] Uploading file:', file);
    const formData = new FormData();
    formData.append('uploadedFile', file, file.name); // must match backend param name

    console.log('[TranslateService] FormData created with file:', file.name);
    return this.http.post(`${this.apiUrl}/upload`, formData);
  }

  sendYoutube(url: string) {
    return this.http.post(`${this.apiUrl}/youtube`, { url });
  }
}
