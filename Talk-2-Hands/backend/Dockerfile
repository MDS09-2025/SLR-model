# =========================
# Build ASP.NET application
# =========================
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build

WORKDIR /src

COPY Talk-2-Hands/backend/*.csproj Talk-2-Hands/backend/
RUN dotnet restore Talk-2-Hands/backend/Talk2Hands.Backend.csproj

COPY Talk-2-Hands/backend/ Talk-2-Hands/backend/

WORKDIR /src/Talk-2-Hands/backend
RUN dotnet publish -c Release -o /app/publish


# =========================
# Runtime
# =========================
FROM mcr.microsoft.com/dotnet/aspnet:8.0

WORKDIR /app

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    libsndfile1 \
    libgl1 \
    libglib2.0-0 \
    libfreetype6-dev \
    libpng-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Create Python virtual environment
RUN python3 -m venv /opt/venv

# Use the virtual environment's Python and pip
ENV PATH="/opt/venv/bin:$PATH"

# Python dependencies
COPY Talk-2-Hands/backend/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

# ASP.NET published application
COPY --from=build /app/publish .

# Python pipeline
COPY src/pipelines /app/src/pipelines

# T5 model
COPY t5-finetuned-aslg /app/t5-finetuned-aslg

# Gloss2Pose data
COPY data/gloss2pose /app/data/gloss2pose

ENV ASPNETCORE_URLS=http://+:8080
ENV ASPNETCORE_ENVIRONMENT=Docker

EXPOSE 8080

ENTRYPOINT ["dotnet", "Talk2Hands.Backend.dll"]