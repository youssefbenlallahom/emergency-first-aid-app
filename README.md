
# 🚑 Monkedh - AI Emergency First Aid Assistant

**Monkedh** is a next-generation emergency response system designed for the **Tunisian context**. It leverages advanced AI agents, Computer Vision, and Real-time Communication to provide immediate, life-saving guidance during medical emergencies.

The system integrates a **CrewAI-powered backend**, a **Next.js frontend**, and specialized modules for **CPR assistance** and **Video Analysis**.

---

## 🌟 Key Features

### 🧠 Specialized AI Emergency Agent
- **Context-Aware**: Expert medical regulator agent ("Régulateur SAMU") trained for Tunisian emergency protocols (190).
- **RAG System**: Retrieves accurate medical protocols from official manuals.
- **Fast Response**: Optimized single-agent architecture for low-latency guidance in critical situations.

### 🗣️ Real-Time Voice Interaction
- Hands-free voice mode powered by **Azure OpenAI GPT-Realtime**.
- Natural conversation flow for high-stress situations.

### 📹 Vision & Video Analysis
- **CPR Assistant**: AI-powered camera tool that monitors CPR quality using **YOLOv8** and computer vision.
- **Video Report**: Microservice-based architecture using **Vision Language Models (VLM)** to analyze crash or emergency videos and generate reports.

### 🖥️ Operator Dashboard
- **Next.js** dashboard for users to interact with the AI assistant via text or voice.

---

## 🏗️ Architecture

The project is divided into a **Backend** (Python microservices) and a **Frontend** (Next.js application).

```mermaid
graph TD
    User[User / Victim] -->|Voice/Text| Frontend
    User -->|Camera Feed| Frontend
    Frontend[Next.js Frontend] -->|API Calls| Backend
    Frontend -->|WebSockets| CPR_AI[CPR AI Assistant]
    
    subgraph Backend Services
        Backend[FastAPI Main Server]
        CrewAI[CrewAI Agent]
        VLM[Realtime VLM Service (Docker)]
        Redis[(Redis Memory)]
        Qdrant[(Qdrant Vector DB)]
        
        Backend --> CrewAI
        CrewAI --> Redis
        CrewAI --> Qdrant
        
        VLM --> VisionServe[Vision Service]
        VLM --> AgentServe[LangChain Agent]
    end
    
    subgraph AI Models
        YOLO[YOLOv8 CPR Detection]
        Azure[Azure OpenAI GPT-4]
    end
    
    CPR_AI --> YOLO
    CrewAI --> Azure
    Backend --> VLM
```

---

## 🛠️ Tech Stack

### Frontend (`/frontend`)
- **Framework**: [Next.js 16](https://nextjs.org/) (App Router)
- **Language**: TypeScript / React 19
- **UI System**: [Shadcn UI](https://ui.shadcn.com/) (Radix Primitives)
- **Styling**: [Tailwind CSS 4](https://tailwindcss.com/)
- **Animations**: [Framer Motion](https://www.framer.com/motion/)

### Backend (`/backend/assistant`)
- **Core Logic**: [CrewAI](https://crewai.com/) (Single specialized agent)
- **LLM Provider**: Azure OpenAI (GPT-4)
- **Vector DB**: [Qdrant](https://qdrant.tech/) with [Ollama](https://ollama.ai/) embeddings
- **Memory**: Redis (Short-term context)
- **Search Tools**: Serper Dev (Google Search), ScrapeWebsiteTool

### Computer Vision Modules
- **CPR Assistant** (`/backend/cpr_assistant`):
    - **YOLOv8** (`ultralytics`)
    - **OpenCV** & **PyTorch**
    - **Flask** API for streaming
- **Realtime VLM** (`/backend/realtime_vlm`):
    - **Dockerized Microservices**
    - **LangChain**
    - Customized Vision Service

---

## 🚀 Getting Started

### Prerequisites

- **Node.js** v18+ and **npm/pnpm**
- **Python** 3.10 - 3.12
- **Redis** server (Local or Cloud)
- **Docker** (for VLM services)
- **Ollama** (for local embeddings)
- **API Keys**: Azure OpenAI, Serper, Qdrant (if cloud)

### 1️⃣ Installation

#### Backend Setup

1.  Navigate to the assistant directory:
    ```bash
    cd backend/assistant
    ```
2.  Create a virtual environment:
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\Activate
    # Linux/Mac
    source venv/bin/activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

#### Frontend Setup

1.  Navigate to the frontend directory:
    ```bash
    cd frontend
    ```
2.  Install dependencies:
    ```bash
    npm install
    # or
    pnpm install
    ```

### 2️⃣ Configuration

Create a `.env` file in `backend/assistant/.env`:

```env
# Azure OpenAI
AZURE_API_KEY=your_key
AZURE_API_BASE=https://your-resource.openai.azure.com/
AZURE_API_VERSION=2024-12-01-preview
model=azure/gpt-4-deployment

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Search Tools
SERPER_API_KEY=your_serper_key
```

---

## 🏃‍♂️ Usage

### Running the Assistant (Text/Voice)

```bash
# In backend/assistant/
python -m monkedh.main          # Text Chat CLI
python -m monkedh.main --voice # Voice Mode
```

### Running the Frontend

```bash
cd frontend
npm run dev
```

Visit `http://localhost:3000` to access the web application.

### Running CPR Assistant

```bash
cd backend/cpr_assistant
python api_server.py
```

### Running VLM Services

```bash
cd backend/realtime_vlm
docker-compose up --build
```

---

## 📂 Project Structure

- **`backend/`**
    - **`assistant/`**: Core CrewAI agent ("Régulateur SAMU"), RAG, and image search tools.
    - **`cpr_assistant/`**: Computer vision logic (`YOLO`) for real-time CPR monitoring.
    - **`realtime_vlm/`**: Dockerized microservices for video analysis (`vision-service`, `agent-service`).
- **`frontend/`**
    - **`app/`**: Next.js App Router structure.
    - **`components/`**: Reusable UI components (Shadcn UI).

---

## 🤝 Contributing

Contributions are welcome! Please ensure you follow the existing code style and structure.

## 📄 License

This project is licensed under the MIT License.

---

**Author**: Youssef Benlallahom
