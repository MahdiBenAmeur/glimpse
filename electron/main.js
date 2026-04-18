const { app, BrowserWindow } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const http = require('http')

let mainWindow
let backendProcess
let viteProcess

const isDev = !app.isPackaged

const BACKEND_URL = 'http://127.0.0.1:8000'
const FRONTEND_URL = 'http://localhost:5173'

// 🔥 Start FastAPI
function startBackend() {
    backendProcess = spawn('python', [
        path.join(__dirname, '../backend/run.py')
    ], { shell: true })

    backendProcess.stdout.on('data', d => console.log(`[FASTAPI]: ${d}`))
    backendProcess.stderr.on('data', d => console.error(`[FASTAPI ERROR]: ${d}`))
}

// ⚛️ Start Vite
function startVite() {
    viteProcess = spawn('npm', ['run', 'dev'], {
        cwd: path.join(__dirname, '../glimpse-front'),
        shell: true
    })

    viteProcess.stdout.on('data', d => console.log(`[VITE]: ${d}`))
    viteProcess.stderr.on('data', d => console.error(`[VITE ERROR]: ${d}`))
}

// ⏳ Wait for Vite
function waitForFrontend(callback) {
    const interval = setInterval(() => {
        http.get(FRONTEND_URL, () => {
            clearInterval(interval)
            callback()
        }).on('error', () => { })
    }, 500)
}

// 🪟 Create window
function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800
    })

    mainWindow.loadURL(FRONTEND_URL)
}

// 🚀 App ready
app.whenReady().then(() => {
    startBackend()
    startVite()

    waitForFrontend(() => {
        createWindow()
    })
})

// 🛑 Cleanup
app.on('will-quit', () => {
    if (backendProcess) backendProcess.kill()
    if (viteProcess) viteProcess.kill()
})