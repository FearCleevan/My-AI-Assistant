/**
 * ChatViewProvider — registers the My AI Assistant as a sidebar view
 * in the Activity Bar (like Claude Code / Copilot), not a split editor panel.
 */
import * as vscode from 'vscode';
import * as fs   from 'fs';
import * as path from 'path';
import { ApiClient, Source } from './ApiClient';

type Message = { role: 'user' | 'assistant'; content: string };

export class ChatViewProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'myai.chatView';

    private _view?: vscode.WebviewView;
    private _client: ApiClient;
    private _history: Message[] = [];
    private _topic:   string    = '';
    private _fileCtx: string    = '';
    private _fileName: string   = '';

    constructor(private readonly _context: vscode.ExtensionContext) {
        const port = vscode.workspace.getConfiguration('myai').get<number>('serverPort', 8765);
        this._client = new ApiClient(port);

        const defaultTopic = vscode.workspace.getConfiguration('myai').get<string>('defaultTopic', '');
        if (defaultTopic) { this._topic = defaultTopic; }

        // Sync active file whenever the user switches tabs
        vscode.window.onDidChangeActiveTextEditor(
            (ed: vscode.TextEditor | undefined) => this._syncFileContext(ed),
            null,
            this._context.subscriptions
        );

        // Rebuild client if port setting changes
        vscode.workspace.onDidChangeConfiguration(
            (e: vscode.ConfigurationChangeEvent) => {
                if (e.affectsConfiguration('myai.serverPort')) {
                    const p = vscode.workspace.getConfiguration('myai').get<number>('serverPort', 8765);
                    this._client = new ApiClient(p);
                    this._checkServer();
                }
            },
            null,
            this._context.subscriptions
        );
    }

    // ── Called by VS Code when the sidebar panel becomes visible ─────────────

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        _ctx:   vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ): void {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._context.extensionUri],
        };

        webviewView.webview.html = this._buildHtml();

        webviewView.webview.onDidReceiveMessage(
            (msg) => this._handleWebviewMessage(msg),
            null,
            this._context.subscriptions
        );

        // Re-sync file context whenever the panel is shown
        webviewView.onDidChangeVisibility(() => {
            if (webviewView.visible) {
                this._syncFileContext(vscode.window.activeTextEditor);
            }
        });
    }

    // ── Public API (called from extension.ts right-click commands) ────────────

    /** Pre-fill the input and focus the sidebar panel. */
    public sendPrompt(prompt: string, extraContext?: string): void {
        if (extraContext) { this._fileCtx = extraContext; }
        // Reveal the sidebar view
        vscode.commands.executeCommand('myai.chatView.focus');
        // Small delay so the webview is ready before we post
        setTimeout(() => {
            this._view?.webview.postMessage({ type: 'setInput', value: prompt });
        }, 150);
    }

    // ── Private helpers ───────────────────────────────────────────────────────

    private _syncFileContext(editor?: vscode.TextEditor): void {
        if (!editor || editor.document.uri.scheme !== 'file') { return; }
        const doc   = editor.document;
        const text  = doc.getText();
        const limit = 20_000;
        this._fileCtx  = text.length > limit ? text.slice(0, limit) + '\n// ... [truncated]' : text;
        this._fileName = doc.fileName.split(/[\\/]/).pop() ?? '';
        this._view?.webview.postMessage({
            type:     'fileContext',
            fileName: this._fileName,
            chars:    this._fileCtx.length,
        });
    }

    private async _checkServer(): Promise<void> {
        try {
            const h = await this._client.getHealth();
            this._view?.webview.postMessage({
                type:    'serverStatus',
                ok:      h.ok,
                message: h.ok
                    ? `Connected  ·  model: ${h.model}`
                    : `Ollama not running  —  run: ollama serve`,
            });
            if (h.ok) { this._autoDetectProject(); }
        } catch {
            this._view?.webview.postMessage({
                type:    'serverStatus',
                ok:      false,
                message: 'Backend not running  —  run: myai serve',
            });
        }
    }

    private async _autoDetectProject(): Promise<void> {
        if (this._topic) { return; }
        const folders = vscode.workspace.workspaceFolders;
        if (!folders?.length) { return; }
        const root = folders[0].uri.fsPath;

        try {
            const projects: any[] = await this._client.getProjects();
            const match = projects.find((p) =>
                root.startsWith(p.root) || p.root.startsWith(root)
            );
            if (match) {
                this._topic = match.topic;
                this._view?.webview.postMessage({
                    type:    'setTopic',
                    topic:   match.topic,
                    message: `Project detected: ${match.name}  (${match.framework})`,
                });
            }
        } catch { /* server not ready */ }
    }

    private _handleWebviewMessage(msg: any): void {
        switch (msg.type) {
            case 'ready':
                this._checkServer();
                this._syncFileContext(vscode.window.activeTextEditor);
                break;
            case 'chat':
                this._sendChat(msg.question);
                break;
            case 'clear':
                this._history = [];
                break;
            case 'setTopic':
                this._topic = msg.topic ?? '';
                break;
        }
    }

    private _sendChat(question: string): void {
        this._history.push({ role: 'user', content: question });
        this._view?.webview.postMessage({ type: 'startResponse' });

        let fullAnswer = '';

        this._client.streamChat(
            {
                question,
                topic:        this._topic,
                history:      this._history.slice(0, -1),
                file_context: this._fileCtx,
            },
            (token) => {
                fullAnswer += token;
                this._view?.webview.postMessage({ type: 'token', token });
            },
            (sources: Source[]) => {
                this._history.push({ role: 'assistant', content: fullAnswer });
                this._view?.webview.postMessage({ type: 'done', sources });
            },
            (err) => {
                this._view?.webview.postMessage({ type: 'error', message: err });
            }
        );
    }

    // ── HTML ──────────────────────────────────────────────────────────────────

    private _buildHtml(): string {
        const htmlPath = path.join(this._context.extensionPath, 'media', 'webview.html');
        return fs.readFileSync(htmlPath, 'utf8');
    }
}
