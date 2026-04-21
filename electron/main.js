const { app, BrowserWindow } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const http = require('http')
const fs = require('fs')

let mainWindow
let backendProcess
let viteProcess

const FRONTEND_URL = 'http://localhost:8080'
const BACKEND_URL = 'http://127.0.0.1:8000'

function resolvePythonCommand() {
    const projectVenvPython = path.join(__dirname, '../desktopvenv/Scripts/python.exe')
    const inheritedVenvPython = process.env.VIRTUAL_ENV
        ? path.join(process.env.VIRTUAL_ENV, 'Scripts', 'python.exe')
        : null

    return process.env.BACKEND_PYTHON
        || (fs.existsSync(projectVenvPython) ? projectVenvPython : null)
        || (inheritedVenvPython && fs.existsSync(inheritedVenvPython) ? inheritedVenvPython : null)
        || 'python'
}

// Start FastAPI
function startBackend() {
    backendProcess = spawn(resolvePythonCommand(), [
        path.join(__dirname, '../server.py')
    ], {
        cwd: path.join(__dirname, '..'),
        shell: false
    })

    backendProcess.stdout.on('data', d => console.log(`[FASTAPI]: ${d}`))
    backendProcess.stderr.on('data', d => console.error(`[FASTAPI ERROR]: ${d}`))
}

function waitForBackend(callback) {
    const maxAttempts = 50
    let attempts = 0

    const interval = setInterval(() => {
        attempts++

        http.get(BACKEND_URL, () => {
            clearInterval(interval)
            console.log('Backend ready')
            callback()
        }).on('error', () => {
            if (attempts >= maxAttempts) {
                clearInterval(interval)
                console.error('Backend did not start in time')
            }
        })
    }, 500)
}

// Start Vite
function startVite() {
    if (process.platform === 'win32') {
        viteProcess = spawn(process.env.ComSpec || 'cmd.exe', ['/d', '/s', '/c', 'npm run dev'], {
            cwd: path.join(__dirname, '../glimpse-front'),
            shell: false
        })
    } else {
        viteProcess = spawn('npm', ['run', 'dev'], {
            cwd: path.join(__dirname, '../glimpse-front'),
            shell: false
        })
    }

    viteProcess.stdout.on('data', d => console.log(`[VITE]: ${d}`))
    viteProcess.stderr.on('data', d => console.error(`[VITE ERROR]: ${d}`))
}

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
                console.error('Vite did not start in time')
            }
        })
    }, 500)
}

// Create window
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

// Kill process tree (important for Windows)
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

// App ready
app.whenReady().then(() => {
    startBackend()

    // Wait for backend FIRST
    waitForBackend(() => {
        // Then start frontend
        startVite()

        // Then wait for frontend
        waitForFrontend(() => {
            createWindow()
        })
    })
})

// Ensure app quits when window is closed
app.on('window-all-closed', () => {
    app.quit()
})

// Cleanup
app.on('will-quit', () => {
    if (backendProcess) killProcessTree(backendProcess.pid)
    if (viteProcess) killProcessTree(viteProcess.pid)
})
