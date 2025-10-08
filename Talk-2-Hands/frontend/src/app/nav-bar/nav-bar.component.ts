import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ThemeService } from '../services/theme.service';  
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-nav-bar',
  imports: [CommonModule, RouterModule],
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
