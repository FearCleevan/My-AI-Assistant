/**
 * My AI Assistant — VS Code extension entry point.
 */
import * as vscode from 'vscode';
import { ChatViewProvider } from './ChatPanel';

export function activate(context: vscode.ExtensionContext): void {

    // ── Register sidebar view provider ───────────────────────────────────────
    const provider = new ChatViewProvider(context);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(ChatViewProvider.viewType, provider, {
            webviewOptions: { retainContextWhenHidden: true },
        })
    );

    // ── Open / focus the chat panel ──────────────────────────────────────────
    context.subscriptions.push(
        vscode.commands.registerCommand('myai.openChat', () => {
            vscode.commands.executeCommand('myai.chatView.focus');
        })
    );

    // ── Explain selected code ────────────────────────────────────────────────
    context.subscriptions.push(
        vscode.commands.registerCommand('myai.explainSelection', () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) { return; }
            const sel = editor.document.getText(editor.selection).trim();
            if (!sel) {
                vscode.window.showWarningMessage('My AI: Select some code first.');
                return;
            }
            const lang = editor.document.languageId;
            provider.sendPrompt(
                `Explain what this ${lang} code does, step by step:\n\`\`\`${lang}\n${sel}\n\`\`\``
            );
        })
    );

    // ── Fix selected code ────────────────────────────────────────────────────
    context.subscriptions.push(
        vscode.commands.registerCommand('myai.fixSelection', () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) { return; }
            const sel = editor.document.getText(editor.selection).trim();
            if (!sel) {
                vscode.window.showWarningMessage('My AI: Select some code first.');
                return;
            }
            const lang = editor.document.languageId;
            provider.sendPrompt(
                `Find and fix any bugs, errors, or issues in this ${lang} code. ` +
                `Show the corrected version with an explanation of what was wrong:\n` +
                `\`\`\`${lang}\n${sel}\n\`\`\``
            );
        })
    );

    // ── Generate tests ───────────────────────────────────────────────────────
    context.subscriptions.push(
        vscode.commands.registerCommand('myai.generateTests', () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) { return; }
            const sel = editor.document.getText(editor.selection).trim();
            if (!sel) {
                vscode.window.showWarningMessage('My AI: Select some code first.');
                return;
            }
            const lang = editor.document.languageId;
            provider.sendPrompt(
                `Write comprehensive unit tests for this ${lang} code. ` +
                `Cover edge cases, error conditions, and typical usage:\n` +
                `\`\`\`${lang}\n${sel}\n\`\`\``
            );
        })
    );

    // ── Refactor selected code ───────────────────────────────────────────────
    context.subscriptions.push(
        vscode.commands.registerCommand('myai.refactorSelection', () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) { return; }
            const sel = editor.document.getText(editor.selection).trim();
            if (!sel) {
                vscode.window.showWarningMessage('My AI: Select some code first.');
                return;
            }
            const lang = editor.document.languageId;
            provider.sendPrompt(
                `Refactor this ${lang} code for better readability, maintainability, ` +
                `and performance. Explain each change you make:\n` +
                `\`\`\`${lang}\n${sel}\n\`\`\``
            );
        })
    );

    // ── Ask about current file ───────────────────────────────────────────────
    context.subscriptions.push(
        vscode.commands.registerCommand('myai.askAboutFile', () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showWarningMessage('My AI: Open a file first.');
                return;
            }
            const fileName = editor.document.fileName.split(/[\\/]/).pop() ?? 'this file';
            provider.sendPrompt(
                `Explain the purpose and structure of ${fileName}. ` +
                `What does it do, how is it organised, and are there any issues I should know about?`
            );
        })
    );
}

export function deactivate(): void {}
