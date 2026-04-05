/**
 * ChatViewProvider — sidebar WebviewView for My AI Assistant.
 * Phase 5: adds @ file picker so users can attach workspace files as context.
 */
import * as vscode from 'vscode';
import * as fs   from 'fs';
import * as path from 'path';
import { ApiClient, Source } from './ApiClient';

type Message = { role: 'user' | 'assistant'; content: string };
type FileEntry = { name: string; relPath: string; absPath: string; ext: string };

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

        vscode.window.onDidChangeActiveTextEditor(
            (ed: vscode.TextEditor | undefined) => this._syncFileContext(ed),
            null,
            this._context.subscriptions
        );

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

    // ── WebviewViewProvider ───────────────────────────────────────────────────

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

        webviewView.onDidChangeVisibility(() => {
            if (webviewView.visible) {
                this._syncFileContext(vscode.window.activeTextEditor);
            }
        });
    }

    // ── Public API ────────────────────────────────────────────────────────────

    public sendPrompt(prompt: string, extraContext?: string): void {
        if (extraContext) { this._fileCtx = extraContext; }
        vscode.commands.executeCommand('myai.chatView.focus');
        setTimeout(() => {
            this._view?.webview.postMessage({ type: 'setInput', value: prompt });
        }, 150);
    }

    // ── Message handler ───────────────────────────────────────────────────────

    private _handleWebviewMessage(msg: any): void {
        switch (msg.type) {
            case 'ready':
                this._checkServer();
                this._syncFileContext(vscode.window.activeTextEditor);
                break;
            case 'chat':
                this._sendChat(msg.question, msg.attachedPaths ?? []);
                break;
            case 'clear':
                this._history = [];
                break;
            case 'setTopic':
                this._topic = msg.topic ?? '';
                break;
            case 'getFiles':
                this._getWorkspaceFiles().then(files => {
                    this._view?.webview.postMessage({ type: 'fileList', files });
                });
                break;
        }
    }

    // ── Workspace file scanner (for @ picker) ─────────────────────────────────

    private async _getWorkspaceFiles(): Promise<FileEntry[]> {
        const excludes = '{**/node_modules/**,**/.git/**,**/dist/**,**/build/**,' +
                         '**/.next/**,**/out/**,**/__pycache__/**,**/vendor/**,' +
                         '**/.venv/**,**/coverage/**,**/*.vsix,**/*.lock}';

        const uris = await vscode.workspace.findFiles('**/*', excludes, 1000);
        const root = (vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? '').replace(/\\/g, '/');

        return uris
            .map(uri => {
                const abs = uri.fsPath.replace(/\\/g, '/');
                const rel = abs.startsWith(root) ? abs.slice(root.length).replace(/^\//, '') : abs;
                const name = rel.split('/').pop() ?? '';
                const ext  = name.includes('.') ? name.split('.').pop()!.toLowerCase() : '';
                return { name, relPath: rel, absPath: uri.fsPath, ext };
            })
            .filter(f => f.name && !f.name.startsWith('.'))
            .sort((a, b) => a.relPath.localeCompare(b.relPath));
    }

    // ── Chat sender ───────────────────────────────────────────────────────────

    private _sendChat(question: string, attachedPaths: string[] = []): void {
        this._history.push({ role: 'user', content: question });
        this._view?.webview.postMessage({ type: 'startResponse' });

        // Build file context: attached files first, then the active editor file
        let fileCtx = '';
        for (const p of attachedPaths) {
            try {
                const content = fs.readFileSync(p, 'utf8');
                const limit   = 15_000;
                const body    = content.length > limit
                    ? content.slice(0, limit) + '\n// ... [truncated]'
                    : content;
                const name    = p.split(/[\\/]/).pop() ?? p;
                fileCtx += `\n\n--- Attached: ${name} ---\n${body}`;
            } catch { /* skip unreadable files */ }
        }
        if (this._fileCtx) {
            fileCtx += `\n\n--- Active file: ${this._fileName || 'current'} ---\n${this._fileCtx}`;
        }

        let fullAnswer = '';

        this._client.streamChat(
            {
                question,
                topic:        this._topic,
                history:      this._history.slice(0, -1),
                file_context: fileCtx,
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

    // ── Helpers ───────────────────────────────────────────────────────────────

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
                    ? `Connected  \u00b7  model: ${h.model}`
                    : `Ollama not running  \u2014  run: ollama serve`,
            });
            if (h.ok) { this._autoDetectProject(); }
        } catch {
            this._view?.webview.postMessage({
                type:    'serverStatus',
                ok:      false,
                message: 'Backend not running  \u2014  run: myai serve',
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

    private _buildHtml(): string {
        const htmlPath = path.join(this._context.extensionPath, 'media', 'webview.html');
        return fs.readFileSync(htmlPath, 'utf8');
    }
}
