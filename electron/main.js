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

function logElectron(scope, message, extra) {
    const timestamp = new Date().toISOString()
    if (extra !== undefined) {
        console.log(`[${timestamp}] [ELECTRON:${scope}] ${message}`, extra)
        return
    }
    console.log(`[${timestamp}] [ELECTRON:${scope}] ${message}`)
}

function logElectronError(scope, message, extra) {
    const timestamp = new Date().toISOString()
    if (extra !== undefined) {
        console.error(`[${timestamp}] [ELECTRON:${scope}] ${message}`, extra)
        return
    }
    console.error(`[${timestamp}] [ELECTRON:${scope}] ${message}`)
}

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
    const pythonCommand = resolvePythonCommand()
    const serverScript = path.join(__dirname, '../server.py')
    const backendCwd = path.join(__dirname, '..')
    logElectron('BACKEND', 'Starting backend process', { pythonCommand, serverScript, backendCwd })

    backendProcess = spawn(pythonCommand, [
        serverScript
    ], {
        cwd: path.join(__dirname, '..'),
        shell: false
    })
    logElectron('BACKEND', `Backend process spawned with pid=${backendProcess.pid ?? 'unknown'}`)

    backendProcess.stdout.on('data', d => console.log(`[FASTAPI]: ${d}`))
    backendProcess.stderr.on('data', d => console.error(`[FASTAPI ERROR]: ${d}`))
    backendProcess.on('error', error => logElectronError('BACKEND', 'Backend process emitted error', error))
    backendProcess.on('exit', (code, signal) => logElectronError('BACKEND', `Backend process exited`, { code, signal }))
    backendProcess.on('close', (code, signal) => logElectronError('BACKEND', `Backend process closed`, { code, signal }))
}

function waitForBackend(callback) {
    const maxAttempts = 50
    let attempts = 0

    const interval = setInterval(() => {
        attempts++
        if (attempts === 1 || attempts % 5 === 0) {
            logElectron('BACKEND', `Waiting for backend health check attempt ${attempts}/${maxAttempts}`)
        }

        http.get(BACKEND_URL, () => {
            clearInterval(interval)
            logElectron('BACKEND', `Backend ready after ${attempts} attempts`)
            callback()
        }).on('error', error => {
            if (attempts >= maxAttempts) {
                clearInterval(interval)
                logElectronError('BACKEND', 'Backend did not start in time', error)
            } else if (attempts === 1 || attempts % 5 === 0) {
                logElectronError('BACKEND', `Backend health check failed on attempt ${attempts}`, error.message)
            }
        })
    }, 500)
}

// Start Vite
function startVite() {
    const frontendCwd = path.join(__dirname, '../glimpse-front')
    logElectron('FRONTEND', 'Starting frontend dev server', { frontendCwd, platform: process.platform })

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
    logElectron('FRONTEND', `Frontend process spawned with pid=${viteProcess.pid ?? 'unknown'}`)

    viteProcess.stdout.on('data', d => console.log(`[VITE]: ${d}`))
    viteProcess.stderr.on('data', d => console.error(`[VITE ERROR]: ${d}`))
    viteProcess.on('error', error => logElectronError('FRONTEND', 'Frontend process emitted error', error))
    viteProcess.on('exit', (code, signal) => logElectronError('FRONTEND', `Frontend process exited`, { code, signal }))
    viteProcess.on('close', (code, signal) => logElectronError('FRONTEND', `Frontend process closed`, { code, signal }))
}

function waitForFrontend(callback) {
    const maxAttempts = 50
    let attempts = 0

    const interval = setInterval(() => {
        attempts++
        if (attempts === 1 || attempts % 5 === 0) {
            logElectron('FRONTEND', `Waiting for frontend health check attempt ${attempts}/${maxAttempts}`)
        }

        http.get(FRONTEND_URL, () => {
            clearInterval(interval)
            logElectron('FRONTEND', `Frontend ready after ${attempts} attempts`)
            callback()
        }).on('error', error => {
            if (attempts >= maxAttempts) {
                clearInterval(interval)
                logElectronError('FRONTEND', 'Vite did not start in time', error)
            } else if (attempts === 1 || attempts % 5 === 0) {
                logElectronError('FRONTEND', `Frontend health check failed on attempt ${attempts}`, error.message)
            }
        })
    }, 500)
}

// Create window
function createWindow() {
    logElectron('WINDOW', 'Creating browser window')
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
    mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
        logElectronError('WINDOW', 'Window failed to load URL', { errorCode, errorDescription, validatedURL })
    })
    mainWindow.webContents.on('did-finish-load', () => {
        logElectron('WINDOW', 'Window finished loading')
    })
    mainWindow.on('closed', () => {
        logElectron('WINDOW', 'Main window closed')
    })
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
    logElectron('APP', 'Electron app is ready')
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
    logElectron('APP', 'All windows closed, quitting app')
    app.quit()
})

// Cleanup
app.on('will-quit', () => {
    logElectron('APP', 'Electron will quit, cleaning up child processes')
    if (backendProcess) killProcessTree(backendProcess.pid)
    if (viteProcess) killProcessTree(viteProcess.pid)
})
