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
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post(`${this.apiUrl}/upload`, formData);
  }
}
