import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AudioTranslationPageComponent } from './audio-translation-page.component';

describe('AudioTranslationPageComponent', () => {
  let component: AudioTranslationPageComponent;
  let fixture: ComponentFixture<AudioTranslationPageComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AudioTranslationPageComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(AudioTranslationPageComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
