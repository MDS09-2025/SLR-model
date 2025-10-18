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
  rotatingTitle = "";
  rotatingText = "";
  isDarkMode = false;
  private titles = [
    "Why Talk-2 Hands?",
    "Reading Boost!",
    "The Bilingual Brain!",
    "Visual Superpower!",
    "A Different World of Words",
    "Language is More Than Text!"
  ]

  private messages = [
    "Many studies document that DHH learners often lag behind hearing peers in reading comprehension",
    "Studies show that for Deaf adults, watching a sign language interpreter alongside text can nearly double their comprehension",
    "Being fluent in American Sign Language (ASL) gives deaf children a powerful foundation, making them stronger English readers later on",
    "The brains of deaf readers often activate visual processing areas more intensely than hearing readers, turning reading into a highly visual skill",
    "For many native signers, learning to read English is like learning a second language that they have never heard spoken",
    "For millions, sign language isn't just an alternative to text—it's the key to deeper, more natural engagement and understanding"
  ];

  private textIndex = 0;
  private textInterval!: ReturnType<typeof setInterval>;

  constructor(
    private translateService: TranslateService,
    private router: Router,
    private theme: ThemeService
  ) {}

  ngOnInit(): void {
    this.theme.isDarkMode$.subscribe(mode => this.isDarkMode = mode);

    this.rotatingText = this.messages[this.textIndex];
    this.rotatingTitle = this.titles[this.textIndex];
    
    this.textInterval = setInterval(() => {
      this.textIndex = (this.textIndex + 1) % this.messages.length;
      this.rotatingText = this.messages[this.textIndex];
      this.rotatingTitle = this.titles[this.textIndex];
    }, 3000);
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
