import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { TranslateService } from '../services/translate.service';
import { timer, EMPTY, forkJoin } from 'rxjs';
import { switchMap, filter, takeUntil, take, catchError } from 'rxjs/operators';
import { ThemeService } from '../services/theme.service';

@Component({
  selector: 'app-loading-page',
  imports: [],
  templateUrl: './loading-page.component.html',
  styleUrl: './loading-page.component.css'
})
export class LoadingPageComponent {
  message = 'Processing your media...';
  isDarkMode = false;

  constructor(
    private translateService: TranslateService,
    private router: Router,
    private theme: ThemeService
  ) {}

  ngOnInit(): void {
    this.theme.isDarkMode$.subscribe(mode => this.isDarkMode = mode);
    const stored = sessionStorage.getItem('media');
    if (!stored) {
      this.message = 'No upload data found.';
      return;
    }

    const mediaData = JSON.parse(stored);
    const jobId = mediaData.jobId;
    const isVideo = mediaData.type === 'video';

    // Poll every 2s until job is done
    timer(0, 2000).pipe(
      switchMap(() => this.translateService.getStatus(jobId)),
      takeUntil(
        timer(0, 2000).pipe(
          switchMap(() => this.translateService.getStatus(jobId)),
          filter((j: any) => j.status === 3), // failed
          take(1)
        )
      ),
      filter((j: any) => j.status === 2),
      take(1),
      switchMap(() =>
        forkJoin({
          transcript: this.translateService.getResult(jobId, 'transcript').pipe(catchError(() => EMPTY)),
          gloss:      this.translateService.getResult(jobId, 'gloss').pipe(catchError(() => EMPTY)),
        })
      )
    ).subscribe({
      next: (results) => {
        const withResults = { ...mediaData, results };
        sessionStorage.setItem('media', JSON.stringify(withResults));
        this.router.navigate([isVideo ? '/video' : '/audio']);
      },
      error: (err) => {
        console.error('Polling failed:', err);
        this.router.navigate([isVideo ? '/video' : '/audio']);
      }
    });
  }
}
