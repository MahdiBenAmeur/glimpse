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
        path.join(__dirname, '../server.py')
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
        titleBarStyle: 'hidden',
        titleBarOverlay: {
            color: 'rgba(0, 0, 0, 0)',
            symbolColor: '#000000ff',

            height: 30
        }
    })

    mainWindow.loadURL(FRONTEND_URL)
}

const { exec } = require('child_process')

// 🧨 Kill process tree (important for Windows)
function killProcessTree(pid) {
    if (!pid) return

    if (process.platform === 'win32') {
        exec(`taskkill /PID ${pid} /T /F`)
    } else {
        try {
            process.kill(-pid)
        } catch (e) { }
    }
}

// 🚀 App ready
app.whenReady().then(() => {
    startBackend()
    startVite()

    waitForFrontend(() => {
        createWindow()
    })
})

// ❗ Ensure app quits when window is closed
app.on('window-all-closed', () => {
    app.quit()
})

// 🛑 Cleanup (this WILL now run)
app.on('will-quit', () => {
    if (backendProcess) killProcessTree(backendProcess.pid)
    if (viteProcess) killProcessTree(viteProcess.pid)
})