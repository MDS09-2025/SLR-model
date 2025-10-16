import { trigger, transition, style, animate } from '@angular/animations';

export const POPUP_ANIMATION = trigger('popupAnimation', [
  transition(':enter', [
    style({ opacity: 0, transform: 'scale(0.9)' }),
    animate('300ms ease-out', style({ opacity: 1, transform: 'scale(1)' })),
  ]),
  transition(':leave', [
    animate('200ms ease-in', style({ opacity: 0, transform: 'scale(0.9)' })),
  ]),
]);