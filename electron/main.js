const { app, BrowserWindow } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const http = require('http')
const fs = require('fs')

let mainWindow
let backendProcess
let viteProcess
let startupPromise = null
let backendStarted = false
let frontendStarted = false
let isCreatingWindow = false

const FRONTEND_URL = 'http://localhost:8080'
const BACKEND_URL = 'http://127.0.0.1:8000'
const APP_ROOT = path.join(__dirname, '..')

const hasSingleInstanceLock = app.requestSingleInstanceLock()
if (!hasSingleInstanceLock) {
    logElectronError('APP', 'Another Electron instance is already running; exiting this one')
    app.quit()
}

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
    const inheritedVenvPython = process.env.VIRTUAL_ENV
        ? path.join(process.env.VIRTUAL_ENV, 'Scripts', 'python.exe')
        : null

    return process.env.BACKEND_PYTHON
        || (inheritedVenvPython && fs.existsSync(inheritedVenvPython) ? inheritedVenvPython : null)
        || 'python'
}

// Start FastAPI
function startBackend() {
    if (backendStarted) {
        logElectron('BACKEND', 'Backend start skipped because it is already starting or started')
        return
    }
    backendStarted = true

    const pythonCommand = resolvePythonCommand()
    const serverScript = path.join(__dirname, '../server.py')
    const backendCwd = APP_ROOT
    logElectron('BACKEND', 'Starting backend process', { pythonCommand, serverScript, backendCwd })

    backendProcess = spawn(pythonCommand, [
        serverScript
    ], {
        cwd: APP_ROOT,
        shell: false
    })
    logElectron('BACKEND', `Backend process spawned with pid=${backendProcess.pid ?? 'unknown'}`)

    backendProcess.stdout.on('data', d => console.log(`[FASTAPI]: ${d}`))
    backendProcess.stderr.on('data', d => console.error(`[FASTAPI ERROR]: ${d}`))
    backendProcess.on('error', error => logElectronError('BACKEND', 'Backend process emitted error', error))
    backendProcess.on('exit', (code, signal) => logElectronError('BACKEND', `Backend process exited`, { code, signal }))
    backendProcess.on('close', (code, signal) => logElectronError('BACKEND', `Backend process closed`, { code, signal }))
}

function waitForService(url, scope, maxAttempts) {
    return new Promise((resolve, reject) => {
        let attempts = 0
        let settled = false
        let inFlight = false

        const finish = (callback) => {
            if (settled) return
            settled = true
            callback()
        }

        const timer = setInterval(() => {
            if (settled || inFlight) {
                return
            }

            attempts++
            inFlight = true

            if (attempts === 1 || attempts % 5 === 0) {
                logElectron(scope, `Waiting for service health check attempt ${attempts}/${maxAttempts}`, { url })
            }

            const request = http.get(url, (response) => {
                response.resume()
                inFlight = false

                if (response.statusCode && response.statusCode >= 200 && response.statusCode < 500) {
                    clearInterval(timer)
                    finish(() => {
                        logElectron(scope, `Service ready after ${attempts} attempts`, { url, statusCode: response.statusCode })
                        resolve()
                    })
                    return
                }

                if (attempts >= maxAttempts) {
                    clearInterval(timer)
                    finish(() => {
                        const error = new Error(`Service returned status ${response.statusCode ?? 'unknown'} at ${url}`)
                        logElectronError(scope, 'Service did not start in time', error.message)
                        reject(error)
                    })
                }
            })

            request.on('error', (error) => {
                inFlight = false
                if (attempts >= maxAttempts) {
                    clearInterval(timer)
                    finish(() => {
                        logElectronError(scope, 'Service did not start in time', error)
                        reject(error)
                    })
                } else if (attempts === 1 || attempts % 5 === 0) {
                    logElectronError(scope, `Service health check failed on attempt ${attempts}`, error.message)
                }
            })
        }, 500)
    })
}

// Start Vite
function startVite() {
    if (frontendStarted) {
        logElectron('FRONTEND', 'Frontend start skipped because it is already starting or started')
        return
    }
    frontendStarted = true

    const frontendCwd = path.join(APP_ROOT, 'glimpse-front')
    logElectron('FRONTEND', 'Starting frontend dev server', { frontendCwd, platform: process.platform })

    if (process.platform === 'win32') {
        viteProcess = spawn(process.env.ComSpec || 'cmd.exe', ['/d', '/s', '/c', 'npm run dev'], {
            cwd: frontendCwd,
            shell: false
        })
    } else {
        viteProcess = spawn('npm', ['run', 'dev'], {
            cwd: frontendCwd,
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

// Create window
function createWindow() {
    if (mainWindow && !mainWindow.isDestroyed()) {
        logElectron('WINDOW', 'Create window skipped because a window already exists')
        if (mainWindow.isMinimized()) {
            mainWindow.restore()
        }
        mainWindow.focus()
        return mainWindow
    }

    if (isCreatingWindow) {
        logElectron('WINDOW', 'Create window skipped because window creation is already in progress')
        return mainWindow
    }

    isCreatingWindow = true
    try {
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
            },
            icon: path.join(__dirname, '../glimpse-front/public/logo.png')
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
            mainWindow = null
            isCreatingWindow = false
        })
        mainWindow.once('ready-to-show', () => {
            isCreatingWindow = false
        })
        return mainWindow
    } catch (error) {
        isCreatingWindow = false
        throw error
    }
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
app.on('second-instance', () => {
    logElectron('APP', 'Second instance requested; focusing existing window')
    if (mainWindow && !mainWindow.isDestroyed()) {
        if (mainWindow.isMinimized()) {
            mainWindow.restore()
        }
        mainWindow.focus()
    }
})

async function bootstrapApp() {
    if (startupPromise) {
        logElectron('APP', 'Bootstrap already running; reusing existing startup promise')
        return startupPromise
    }

    startupPromise = (async () => {
        logElectron('APP', 'Electron app is ready')
        startBackend()
        await waitForService(BACKEND_URL, 'BACKEND', 200)
        startVite()
        await waitForService(FRONTEND_URL, 'FRONTEND', 50)
        createWindow()
    })()

    try {
        await startupPromise
    } catch (error) {
        startupPromise = null
        logElectronError('APP', 'Bootstrap failed', error)
        throw error
    }
}

app.whenReady().then(() => {
    return bootstrapApp()
})

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow()
    }
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
