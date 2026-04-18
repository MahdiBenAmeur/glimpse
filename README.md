# Glimpse
A fully local desktop app for semantic and similarity-based image search.

## Development Setup

To run the application locally, you'll need to start the backend, frontend, and Electron framework. The `main.js` electron file automatically manages launching the Python backend and the Vite frontend.

### 1. Backend Setup
Make sure you have all dependencies installed.
```bash
# Activate your virtual environment
hello\Scripts\Activate.ps1

# Install the Python dependencies
pip install -r requirements.txt
```

### 2. Frontend & Electron Setup
Ensure the frontend and electron dependencies are installed:
```bash
# Install frontend packages
cd glimpse-front
npm install
cd ..

# Install electron packages
cd electron
npm install
cd ..
```

### 3. Running the App
Once everything is installed, you can start the complete app using Electron:
```bash
cd electron
npx electron .
```
Note: Electron will automatically orchestrate your FastAPI backend and the Vite server.
