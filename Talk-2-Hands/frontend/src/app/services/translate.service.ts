import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class TranslateService {
  private apiUrl = '/api/translate'; // match backend URL

  constructor(private http: HttpClient) {}

  sendLink(url: string) {
    return this.http.post(`${this.apiUrl}/link`, { url });
  }

  uploadFile(file: File) {
    const formData = new FormData();
    formData.append('uploadedFile', file, file.name);
    
    return this.http.post(`${this.apiUrl}/upload`, formData, {
      reportProgress: true,
      observe: 'events'
    });
  }

  sendYoutube(url: string) {
    return this.http.post(`${this.apiUrl}/youtube`, { url });
  }

  getStatus(jobId: string) {
    return this.http.get(`${this.apiUrl}/status/${jobId}`);
  }

  getResult(jobId: string, which: 'transcript' | 'gloss') {
    return this.http.get(`${this.apiUrl}/result/${jobId}/${which}`, { responseType: 'text' });
  }

  downloadFile(jobId: string, fileName: string) {
    return this.http.get(`${this.apiUrl}/download/${jobId}/${fileName}`, {
      responseType: 'blob'  // 👈 important: get binary file
    });
  }

  getPoseVideo(jobId: string) {
    return this.http.get(`${this.apiUrl}/download/${jobId}/${jobId}.mp4`, {
      responseType: 'blob'
    });
  }

  getPoseTiming(jobId: string) {
  return this.http.get<any[]>(`/jobs/${jobId}/Pose_Output/pose_timing.json`);
}

getTranscript(jobId: string) {
  return this.http.get(`/jobs/${jobId}/transcription_output.txt`, { responseType: 'text' });
}
}
