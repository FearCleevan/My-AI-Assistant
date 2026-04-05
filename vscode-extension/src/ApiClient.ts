/**
 * ApiClient — HTTP client for the My AI Agent backend server.
 * Uses Node's built-in `http` module so no extra dependencies are needed.
 */
import * as http from 'http';

export interface ChatParams {
    question:     string;
    topic?:       string;
    history?:     Array<{ role: string; content: string }>;
    file_context?: string;
    model?:       string;
}

export interface Source {
    num:   number;
    title: string;
    url:   string;
}

export class ApiClient {
    private readonly _port: number;

    constructor(port: number = 8765) {
        this._port = port;
    }

    // ── GET helper ────────────────────────────────────────────────────────────

    private _get(path: string): Promise<any> {
        return new Promise((resolve, reject) => {
            const req = http.get(
                { hostname: '127.0.0.1', port: this._port, path },
                (res) => {
                    let data = '';
                    res.on('data', (chunk) => { data += chunk.toString(); });
                    res.on('end', () => {
                        try { resolve(JSON.parse(data)); }
                        catch { reject(new Error(`Invalid JSON from ${path}`)); }
                    });
                }
            );
            req.setTimeout(5000, () => { req.destroy(); reject(new Error('timeout')); });
            req.on('error', reject);
        });
    }

    // ── Endpoints ─────────────────────────────────────────────────────────────

    async getHealth(): Promise<{ ok: boolean; model: string; reason: string }> {
        return this._get('/health');
    }

    async getTopics(): Promise<any[]> {
        const r = await this._get('/topics');
        return r.topics ?? [];
    }

    async getProjects(): Promise<any[]> {
        const r = await this._get('/projects');
        return r.projects ?? [];
    }

    async getModels(): Promise<string[]> {
        const r = await this._get('/models');
        return r.models ?? [];
    }

    /**
     * Stream a chat response via Server-Sent Events.
     * Calls onToken for each streamed token, onDone when finished.
     */
    streamChat(
        params:  ChatParams,
        onToken: (token: string) => void,
        onDone:  (sources: Source[]) => void,
        onError: (msg: string) => void
    ): void {
        const body = Buffer.from(JSON.stringify(params));

        const req = http.request(
            {
                hostname: '127.0.0.1',
                port:     this._port,
                path:     '/chat/stream',
                method:   'POST',
                headers:  {
                    'Content-Type':   'application/json',
                    'Content-Length': body.byteLength,
                    'Accept':         'text/event-stream',
                },
            },
            (res) => {
                let buffer = '';

                res.on('data', (chunk: Buffer) => {
                    buffer += chunk.toString();
                    // Process complete SSE lines
                    const lines = buffer.split('\n');
                    buffer = lines.pop() ?? '';   // keep incomplete last line

                    for (const line of lines) {
                        if (!line.startsWith('data: ')) { continue; }
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.token !== undefined) {
                                onToken(data.token);
                            } else if (data.done) {
                                onDone(data.sources ?? []);
                            } else if (data.error) {
                                onError(data.error);
                            }
                        } catch { /* malformed line — skip */ }
                    }
                });

                res.on('error', (err) => onError(err.message));
                res.on('end',   () => {/* stream closed normally */});
            }
        );

        req.setTimeout(180_000, () => {
            req.destroy();
            onError('Request timed out (180 s).');
        });
        req.on('error', (err) => onError(err.message));
        req.write(body);
        req.end();
    }
}
