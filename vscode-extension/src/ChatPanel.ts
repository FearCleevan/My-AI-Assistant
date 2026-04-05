/**
 * ChatViewProvider — sidebar WebviewView for My AI Assistant.
 * Phase 5: @ file picker for multi-file context.
 * Phase 6: AI file proposals with Accept / Diff / Reject.
 */
import * as vscode from 'vscode';
import * as fs   from 'fs';
import * as path from 'path';
import { ApiClient, Source } from './ApiClient';

type Message   = { role: 'user' | 'assistant'; content: string };
type FileEntry = { name: string; relPath: string; absPath: string; ext: string };

// ── TextDocumentContentProvider for diff view ─────────────────────────────────

class ProposedContentProvider implements vscode.TextDocumentContentProvider {
    private _onDidChange = new vscode.EventEmitter<vscode.Uri>();
    readonly onDidChange  = this._onDidChange.event;
    private _store        = new Map<string, string>(); // id → content

    set(id: string, content: string): void    { this._store.set(id, content); }
    delete(id: string): void                  { this._store.delete(id); }
    has(id: string): boolean                  { return this._store.has(id); }

    provideTextDocumentContent(uri: vscode.Uri): string {
        // URI: myai-proposed://proposal/<id>
        const id = uri.authority + uri.path.replace(/^\//, '');
        return this._store.get(id) ?? '';
    }

    refresh(id: string): void {
        this._onDidChange.fire(vscode.Uri.parse(`myai-proposed://${id}`));
    }
}

// ── Main provider ─────────────────────────────────────────────────────────────

export class ChatViewProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'myai.chatView';

    private _view?:            vscode.WebviewView;
    private _client:           ApiClient;
    private _history:          Message[] = [];
    private _topic:            string    = '';
    private _fileCtx:          string    = '';
    private _fileName:         string    = '';
    private _contentProvider:  ProposedContentProvider;
    private _retryTimer?:      ReturnType<typeof setInterval>;

    constructor(private readonly _context: vscode.ExtensionContext) {
        const port = vscode.workspace.getConfiguration('myai').get<number>('serverPort', 8765);
        this._client = new ApiClient(port);

        const defaultTopic = vscode.workspace.getConfiguration('myai').get<string>('defaultTopic', '');
        if (defaultTopic) { this._topic = defaultTopic; }

        // Register the diff content provider
        this._contentProvider = new ProposedContentProvider();
        _context.subscriptions.push(
            vscode.workspace.registerTextDocumentContentProvider('myai-proposed', this._contentProvider)
        );

        vscode.window.onDidChangeActiveTextEditor(
            (ed: vscode.TextEditor | undefined) => this._syncFileContext(ed),
            null, _context.subscriptions
        );

        vscode.workspace.onDidChangeConfiguration(
            (e: vscode.ConfigurationChangeEvent) => {
                if (e.affectsConfiguration('myai.serverPort')) {
                    const p = vscode.workspace.getConfiguration('myai').get<number>('serverPort', 8765);
                    this._client = new ApiClient(p);
                    this._checkServer();
                }
            },
            null, _context.subscriptions
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
            null, this._context.subscriptions
        );

        webviewView.onDidChangeVisibility(() => {
            if (webviewView.visible) { this._syncFileContext(vscode.window.activeTextEditor); }
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

    // ── Message dispatcher ────────────────────────────────────────────────────

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

            case 'reconnect':
                this._checkServer();
                break;

            // Phase 5 — @ file picker
            case 'getFiles':
                this._getWorkspaceFiles().then(files => {
                    this._view?.webview.postMessage({ type: 'fileList', files });
                });
                break;

            // Phase 6 — file proposals
            case 'registerProposals':
                for (const p of (msg.proposals ?? [])) {
                    this._contentProvider.set(p.id, p.content);
                }
                break;
            case 'acceptFile':
                this._acceptFile(msg.id, msg.path, msg.content);
                break;
            case 'viewDiff':
                this._showDiff(msg.id, msg.path, msg.content);
                break;
            case 'rejectFile':
                this._contentProvider.delete(msg.id);
                break;
        }
    }

    // ── Phase 6: file operations ──────────────────────────────────────────────

    private _resolveAbsPath(relPath: string): string {
        if (path.isAbsolute(relPath)) { return relPath; }
        const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? '';
        return path.join(root, relPath);
    }

    private async _acceptFile(id: string, relPath: string, content: string): Promise<void> {
        const absPath = this._resolveAbsPath(relPath);
        try {
            const dir = path.dirname(absPath);
            if (!fs.existsSync(dir)) { fs.mkdirSync(dir, { recursive: true }); }
            fs.writeFileSync(absPath, content, 'utf8');
            this._contentProvider.delete(id);

            const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(absPath));
            await vscode.window.showTextDocument(doc, { preview: false });

            this._view?.webview.postMessage({ type: 'fileWritten', id, path: relPath });
            vscode.window.showInformationMessage(`My AI: Saved ${relPath}`);
        } catch (err: any) {
            this._view?.webview.postMessage({ type: 'fileError', id, message: err.message });
            vscode.window.showErrorMessage(`My AI: Could not write ${relPath}: ${err.message}`);
        }
    }

    private async _showDiff(id: string, relPath: string, content: string): Promise<void> {
        const absPath  = this._resolveAbsPath(relPath);
        const fileName = path.basename(relPath);

        this._contentProvider.set(id, content);
        this._contentProvider.refresh(id);

        const proposedUri = vscode.Uri.parse(`myai-proposed://${id}`);

        if (fs.existsSync(absPath)) {
            await vscode.commands.executeCommand(
                'vscode.diff',
                vscode.Uri.file(absPath),
                proposedUri,
                `${fileName}  \u2014  Current \u2194 AI Proposal`
            );
        } else {
            // New file — just open the proposed content
            const doc = await vscode.workspace.openTextDocument(proposedUri);
            await vscode.window.showTextDocument(doc);
        }
    }

    // ── Phase 5: workspace file scanner ──────────────────────────────────────

    private async _getWorkspaceFiles(): Promise<FileEntry[]> {
        const excludes =
            '{**/node_modules/**,**/.git/**,**/dist/**,**/build/**,' +
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

    // ── Chat ──────────────────────────────────────────────────────────────────

    private _sendChat(question: string, attachedPaths: string[] = []): void {
        this._history.push({ role: 'user', content: question });
        this._view?.webview.postMessage({ type: 'startResponse' });

        let fileCtx = '';
        for (const p of attachedPaths) {
            try {
                const text  = fs.readFileSync(p, 'utf8');
                const limit = 15_000;
                const body  = text.length > limit ? text.slice(0, limit) + '\n// ... [truncated]' : text;
                const name  = p.split(/[\\/]/).pop() ?? p;
                fileCtx += `\n\n--- Attached: ${name} ---\n${body}`;
            } catch { /* skip unreadable */ }
        }
        if (this._fileCtx) {
            fileCtx += `\n\n--- Active file: ${this._fileName || 'current'} ---\n${this._fileCtx}`;
        }

        let fullAnswer = '';
        this._client.streamChat(
            { question, topic: this._topic, history: this._history.slice(0, -1), file_context: fileCtx },
            (token) => {
                fullAnswer += token;
                this._view?.webview.postMessage({ type: 'token', token });
            },
            (sources: Source[]) => {
                this._history.push({ role: 'assistant', content: fullAnswer });
                this._view?.webview.postMessage({ type: 'done', sources });
            },
            (err) => { this._view?.webview.postMessage({ type: 'error', message: err }); }
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
            type: 'fileContext', fileName: this._fileName, chars: this._fileCtx.length,
        });
    }

    private async _checkServer(): Promise<void> {
        try {
            const h = await this._client.getHealth();
            // Connected — clear any retry timer
            if (this._retryTimer) {
                clearInterval(this._retryTimer);
                this._retryTimer = undefined;
            }
            this._view?.webview.postMessage({
                type: 'serverStatus', ok: h.ok,
                message: h.ok
                    ? `Connected \u00b7 model: ${h.model}`
                    : `Ollama not running \u2014 run: ollama serve`,
            });
            if (h.ok) { this._autoDetectProject(); }
        } catch (err: any) {
            // Start auto-retry every 15 s so the panel reconnects automatically
            if (!this._retryTimer) {
                this._retryTimer = setInterval(() => this._checkServer(), 15_000);
            }
            const detail = err?.message ?? String(err);
            this._view?.webview.postMessage({
                type: 'serverStatus', ok: false,
                message: `Backend not running \u2014 run: myai serve  (${detail})`,
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
            const match = projects.find(p => root.startsWith(p.root) || p.root.startsWith(root));
            if (match) {
                this._topic = match.topic;
                this._view?.webview.postMessage({
                    type: 'setTopic', topic: match.topic,
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
