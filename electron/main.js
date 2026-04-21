const { app, BrowserWindow } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const http = require('http')

let mainWindow
let backendProcess
let viteProcess

const FRONTEND_URL = 'http://localhost:8080'

// 🔥 Start FastAPI
function startBackend() {
    backendProcess = spawn('python', [
        path.join(__dirname, '../backend/server.py')
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

// ⏳ Wait for Vite server
function waitForFrontend(callback) {
    const maxAttempts = 50
    let attempts = 0

    const interval = setInterval(() => {
        attempts++

        http.get(FRONTEND_URL, () => {
            clearInterval(interval)
            callback()
        }).on('error', () => {
            if (attempts >= maxAttempts) {
                clearInterval(interval)
                console.error('❌ Vite did not start in time')
            }
        })
    }, 500)
}

// 🪟 Create window
function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        autoHideMenuBar: true,
        closable: true,
        fullscreenable: true,
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