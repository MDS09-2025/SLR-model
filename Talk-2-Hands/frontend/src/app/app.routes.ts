import { Routes } from '@angular/router';
import { MainPageComponent } from './main-page/main-page.component';
import { AudioTranslationPageComponent } from './audio-translation-page/audio-translation-page.component';
import { VideoTranslationPageComponent } from './video-translation-page/video-translation-page.component';
import { LoadingPageComponent } from './loading-page/loading-page.component';

export const routes: Routes = [
    { path: '', component: MainPageComponent },
    { path: 'audio', component: AudioTranslationPageComponent},
    { path: 'video', component: VideoTranslationPageComponent},
    { path: 'loading', component: LoadingPageComponent },
];
