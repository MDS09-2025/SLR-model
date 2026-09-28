# Talk2Hands 🤟

Talk2Hands is a Sign Language Recognition (SLR) system that processes hand gestures and converts them into meaningful outputs using machine learning techniques.

---

## 🚀 Quick Start (Docker)

### Prerequisites
Before running Talk2Hands, make sure you have:

- Docker Desktop installed
- Docker Desktop launched and running

### To run the application:

#### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd SLR-model/Talk-2-Hands/backend
```

#### 2. Build the Docker Image
```bash
docker build -t talk2hands -f Talk-2-Hands/backend/Dockerfile .
```

#### 3. Run the Application
```bash
docker run -d -p 5027:8080 --name talk2hands talk2hands
```

#### 4. Open the Application
```bash
http://localhost:5027
``` 
> 💡 **Tip:** A sample video is provided in the `sample-video` directory. You can upload it to the application to quickly try out the Sign Language Recognition feature.
