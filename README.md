# Talk2Hands 🤟

Talk2Hands is a Sign Language Recognition (SLR) system that processes hand gestures and converts them into meaningful outputs using machine learning techniques.

## 🚀 Getting Started

### Run using Docker

#### 1. Install Docker
Make sure Docker is installed on your machine.

#### 2. Clone the repository
#### 3. Build and run the container
#### 4. Open in browser

```bash
git clone <your-repo-url>
cd SLR-model

cd Talk-2-Hands/backend
docker build -t talk2hands .
docker run -p 8080:8080 talk2hands

# Open in browser
http://localhost:8080