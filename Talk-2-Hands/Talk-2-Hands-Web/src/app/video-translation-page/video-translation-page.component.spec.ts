import { ComponentFixture, TestBed } from '@angular/core/testing';

import { VideoTranslationPageComponent } from './video-translation-page.component';

describe('VideoTranslationPageComponent', () => {
  let component: VideoTranslationPageComponent;
  let fixture: ComponentFixture<VideoTranslationPageComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [VideoTranslationPageComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(VideoTranslationPageComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
