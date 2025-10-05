import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ThemeService } from '../services/theme.service';  

@Component({
  selector: 'app-nav-bar',
  imports: [CommonModule],
  templateUrl: './nav-bar.component.html',
  styleUrl: './nav-bar.component.css'
})
export class NavBarComponent {
  isDarkMode = false;

  constructor(private theme: ThemeService) {}

  ngOnInit(): void {
    this.theme.isDarkMode$.subscribe(mode => this.isDarkMode = mode);
  }

  toggleTheme(): void {
    this.theme.toggleTheme();
  }
}
