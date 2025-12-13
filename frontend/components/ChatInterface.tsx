'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowUp, User, Sparkles, StopCircle } from 'lucide-react';
import { fetchAPI } from '@/utils/api';
import { cn } from '@/utils/cn';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

interface Message {
    role: 'user' | 'assistant';
    content: string;
    timestamp?: string;
}

interface ChatInterfaceProps {
    chatbotType: 'SOP' | 'INSW' | 'OTHERS';
    sessionId: string;
    initialMessages: Message[];
    onMessageSent?: () => void;
}

export function ChatInterface({ chatbotType, sessionId, initialMessages, onMessageSent }: ChatInterfaceProps) {
    const [messages, setMessages] = useState<Message[]>(initialMessages);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    useEffect(() => {
        setMessages(initialMessages);
    }, [initialMessages, sessionId]);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, loading]);

    // Auto-resize textarea
    const adjustTextareaHeight = useCallback(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = 'auto';
            textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
        }
    }, []);

    useEffect(() => {
        adjustTextareaHeight();
    }, [input, adjustTextareaHeight]);

    const handleSend = async (e?: React.FormEvent) => {
        e?.preventDefault();
        if (!input.trim() || loading || !sessionId) return;

        const userMsg = input.trim();
        setInput('');
        setLoading(true);

        setMessages(prev => [...prev, { role: 'user', content: userMsg }]);

        try {
            let endpoint = '/chat/sop';
            if (chatbotType === 'INSW') endpoint = '/chat/insw';
            if (chatbotType === 'OTHERS') endpoint = '/chat/others';

            const res = await fetchAPI(endpoint, {
                method: 'POST',
                body: JSON.stringify({
                    message: { role: 'user', content: userMsg },
                    session_id: sessionId
                })
            });

            if (!res.ok) throw new Error('Failed to send message');

            const data = await res.json();
            setMessages(prev => [...prev, data]);
            if (onMessageSent) onMessageSent();

        } catch (err) {
            console.error(err);
            setMessages(prev => [...prev, { role: 'assistant', content: '❌ Failed to get response. Please try again.' }]);
        } finally {
            setLoading(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    // Render markdown content with special handling for links
    const renderContent = (content: string) => {
        const parts = content.split('<CASE_DATA>');
        const textPart = parts[0];
        const caseDataStr = parts[1];

        let caseData = null;
        if (caseDataStr) {
            try {
                caseData = JSON.parse(caseDataStr);
            } catch (e) {
                console.error("Failed to parse case data", e);
            }
        }

        return (
            <div className="prose prose-neutral dark:prose-invert prose-sm max-w-none">
                <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                        // Links - handle download URLs with auth
                        // eslint-disable-next-line @typescript-eslint/no-unused-vars
                        a: ({ node, ...props }) => {
                            const href = props.href || '';
                            // Use proxy route for all backend API calls
                            const API_PROXY = '/api/proxy';

                            // Handle /download-link?filename=xxx URLs - use fetch+blob for correct filename
                            if (href.startsWith('/download-link?')) {
                                const urlParams = new URLSearchParams(href.split('?')[1] || '');
                                const filename = decodeURIComponent(urlParams.get('filename') || 'download');
                                const fullHref = `${API_PROXY}${href}`;

                                const handleDownload = (e: React.MouseEvent) => {
                                    e.preventDefault();
                                    // Append timestamp to prevent browser from using cached Redirects
                                    // This forces it to hit the backend Proxy again
                                    const cacheBuster = `&_t=${Date.now()}`;
                                    const finalUrl = fullHref + cacheBuster;
                                    window.location.href = finalUrl;
                                };

                                return (
                                    <a
                                        {...props}
                                        href={fullHref}
                                        onClick={handleDownload}
                                        className="text-foreground underline hover:no-underline font-medium cursor-pointer"
                                    >
                                        {props.children}
                                    </a>
                                );
                            }

                            // Handle legacy /download/{token} URLs - also use fetch+blob
                            if (href.startsWith('/download/')) {
                                const fullHref = `${API_PROXY}${href}`;

                                const handleDownload = (e: React.MouseEvent) => {
                                    e.preventDefault();
                                    const cacheBuster = `?_t=${Date.now()}`; // URL might not have params yet
                                    window.location.href = fullHref + cacheBuster;
                                };

                                return (
                                    <a
                                        {...props}
                                        href={fullHref}
                                        onClick={handleDownload}
                                        className="text-foreground underline hover:no-underline font-medium cursor-pointer"
                                    >
                                        {props.children}
                                    </a>
                                );
                            }

                            return <a {...props} href={href} className="text-foreground underline hover:no-underline font-medium" target="_blank" rel="noopener noreferrer" />;
                        },
                        // Paragraphs - theme-aware
                        // eslint-disable-next-line @typescript-eslint/no-unused-vars
                        p: ({ node, ...props }) => <p className="mb-4 last:mb-0 leading-relaxed text-foreground" {...props} />,
                        // Lists - theme-aware
                        // eslint-disable-next-line @typescript-eslint/no-unused-vars
                        ul: ({ node, ...props }) => <ul className="mb-4 last:mb-0 pl-5 space-y-1.5 list-disc marker:text-muted-foreground" {...props} />,
                        // eslint-disable-next-line @typescript-eslint/no-unused-vars
                        ol: ({ node, ...props }) => <ol className="mb-4 last:mb-0 pl-5 space-y-1.5 list-decimal marker:text-muted-foreground" {...props} />,
                        // eslint-disable-next-line @typescript-eslint/no-unused-vars
                        li: ({ node, ...props }) => <li className="leading-relaxed text-foreground" {...props} />,
                        // Headers - theme-aware
                        // eslint-disable-next-line @typescript-eslint/no-unused-vars
                        h1: ({ node, ...props }) => <h1 className="text-2xl font-bold text-foreground mb-3 mt-5 first:mt-0 pb-2 border-b border-border" {...props} />,
                        // eslint-disable-next-line @typescript-eslint/no-unused-vars
                        h2: ({ node, ...props }) => <h2 className="text-xl font-semibold text-foreground mb-2.5 mt-4 first:mt-0" {...props} />,
                        // eslint-disable-next-line @typescript-eslint/no-unused-vars
                        h3: ({ node, ...props }) => <h3 className="text-lg font-semibold text-foreground mb-2 mt-3 first:mt-0" {...props} />,
                        // eslint-disable-next-line @typescript-eslint/no-unused-vars
                        h4: ({ node, ...props }) => <h4 className="text-base font-semibold text-foreground mb-1.5 mt-2 first:mt-0" {...props} />,
                        // Bold text - theme-aware
                        // eslint-disable-next-line @typescript-eslint/no-unused-vars
                        strong: ({ node, ...props }) => <strong className="font-semibold text-foreground" {...props} />,
                        // Horizontal rule - theme-aware
                        // eslint-disable-next-line @typescript-eslint/no-unused-vars
                        hr: ({ node, ...props }) => <hr className="my-4 border-border" {...props} />,
                        // Blockquote - theme-aware
                        // eslint-disable-next-line @typescript-eslint/no-unused-vars
                        blockquote: ({ node, ...props }) => <blockquote className="border-l-3 border-border pl-4 my-4 text-muted-foreground italic" {...props} />,
                        // Code - theme-aware
                        // eslint-disable-next-line @typescript-eslint/no-unused-vars
                        code: ({ node, className, children, ...props }) => {
                            const match = /language-(\w+)/.exec(className || '');
                            const isInline = !match;
                            return isInline ? (
                                <code className="px-1.5 py-0.5 bg-muted rounded text-sm font-mono text-foreground" {...props}>
                                    {children}
                                </code>
                            ) : (
                                <code className={cn("block p-3 bg-muted rounded-lg overflow-x-auto text-sm font-mono", className)} {...props}>
                                    {children}
                                </code>
                            );
                        }
                    }}
                >
                    {textPart}
                </ReactMarkdown>

                {caseData && Array.isArray(caseData) && (
                    <div className="mt-4 border border-border rounded-lg overflow-hidden">
                        <div className="bg-muted px-4 py-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                            Related Cases
                        </div>
                        <div className="overflow-x-auto">
                            <table className="min-w-full divide-y divide-border text-sm">
                                <thead className="bg-muted/50">
                                    <tr>
                                        <th className="px-4 py-2 text-left font-medium text-muted-foreground">Case No</th>
                                        <th className="px-4 py-2 text-left font-medium text-muted-foreground">Question</th>
                                        <th className="px-4 py-2 text-left font-medium text-muted-foreground">Answer</th>
                                    </tr>
                                </thead>
                                <tbody className="bg-background divide-y divide-border">
                                    {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                                    {caseData.map((caseItem: any, i: number) => (
                                        <tr key={i}>
                                            <td className="px-4 py-2 whitespace-nowrap font-mono text-foreground">{caseItem.case_no}</td>
                                            <td className="px-4 py-2 text-foreground">{caseItem.question}</td>
                                            <td className="px-4 py-2 text-foreground">{caseItem.answer}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </div>
        );
    };

    // ... existing imports
    // ...

    return (
        <div className="h-full relative overflow-hidden bg-background">
            {/* Messages Container - Scrollable with bottom padding for input */}
            <div ref={scrollRef} className="absolute inset-0 bottom-[140px] overflow-y-auto scroll-smooth scrollbar-thin">
                <div className="w-full max-w-3xl xl:max-w-4xl 2xl:max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                    {messages.length === 0 && (
                        <motion.div
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ duration: 0.5 }}
                            className="flex flex-col items-center justify-center h-full min-h-[400px] text-center"
                        >
                            <div className="w-12 h-12 rounded-full flex items-center justify-center mb-4 bg-muted">
                                <Sparkles className="w-6 h-6 text-foreground" />
                            </div>
                            <h2 className="text-xl font-semibold text-foreground mb-2">
                                {chatbotType === 'SOP' ? 'SOP Assistant' :
                                    chatbotType === 'INSW' ? 'HS Code Assistant' :
                                        'General EXIM Assistant'}
                            </h2>
                            <p className="text-muted-foreground max-w-md">
                                {chatbotType === 'SOP'
                                    ? 'Ask questions about Standard Operating Procedures and EXIM compliance.'
                                    : chatbotType === 'INSW'
                                        ? 'Search HS Codes, import/export regulations, and HS Code database.'
                                        : 'Ask about General EXIM knowledge and Panarub internal documents.'}
                            </p>
                        </motion.div>
                    )}

                    <AnimatePresence initial={false}>
                        <div className="space-y-6">
                            {messages.map((msg, idx) => (
                                <motion.div
                                    key={`${sessionId}-${idx}`}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.2 }}
                                    className="group"
                                >
                                    {/* ... existing message layout ... */}
                                    <div className={cn(
                                        "flex gap-4 relative",
                                        msg.role === 'user' ? "flex-row-reverse" : "flex-row"
                                    )}>
                                        <div className={cn(
                                            "w-8 h-8 rounded-full flex items-center justify-center shrink-0",
                                            msg.role === 'user' ? "bg-primary" : "bg-muted"
                                        )}>
                                            {msg.role === 'user'
                                                ? <User className="w-4 h-4 text-primary-foreground" />
                                                : <Sparkles className="w-4 h-4 text-foreground" />
                                            }
                                        </div>

                                        <div className={cn(
                                            "flex-1 min-w-0 max-w-[85%]",
                                            msg.role === 'user' ? "text-right" : "text-left"
                                        )}>
                                            <div className={cn(
                                                "inline-block px-4 py-3 rounded-2xl text-left relative group-hover:shadow-md transition-shadow duration-200",
                                                msg.role === 'user' ? "bg-primary text-primary-foreground rounded-tr-md" : "bg-muted text-foreground rounded-tl-md"
                                            )}>
                                                {msg.role === 'user' ? (
                                                    <div className="whitespace-pre-wrap">{msg.content}</div>
                                                ) : (
                                                    renderContent(msg.content)
                                                )}

                                                {/* Action Buttons */}
                                                <div className={cn(
                                                    "absolute top-0 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center gap-1 bg-background/80 backdrop-blur-sm rounded-md shadow-sm border border-border p-0.5",
                                                    msg.role === 'user' ? "-left-16" : "-right-16"
                                                )}>
                                                    <TooltipProvider>
                                                        <Tooltip>
                                                            <TooltipTrigger asChild>
                                                                <button
                                                                    onClick={() => {
                                                                        // Strip all markdown formatting
                                                                        let plainText = msg.content
                                                                            // Remove links: [text](url) -> text
                                                                            .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
                                                                            // Remove headers: # ## ### etc
                                                                            .replace(/^#{1,6}\s+/gm, '')
                                                                            // Remove bold: **text** or __text__ -> text
                                                                            .replace(/\*\*([^*]+)\*\*/g, '$1')
                                                                            .replace(/__([^_]+)__/g, '$1')
                                                                            // Remove italic: *text* or _text_ -> text
                                                                            .replace(/\*([^*]+)\*/g, '$1')
                                                                            .replace(/_([^_]+)_/g, '$1')
                                                                            // Remove inline code: `code` -> code
                                                                            .replace(/`([^`]+)`/g, '$1')
                                                                            // Remove list markers: - or * or 1.
                                                                            .replace(/^[\s]*[-*]\s+/gm, '')
                                                                            .replace(/^[\s]*\d+\.\s+/gm, '')
                                                                            // Clean up extra whitespace
                                                                            .replace(/\n{3,}/g, '\n\n');
                                                                        navigator.clipboard.writeText(plainText);
                                                                    }}
                                                                    className="p-1.5 hover:bg-accent rounded-sm text-muted-foreground hover:text-foreground cursor-pointer"
                                                                >
                                                                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2" /><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" /></svg>
                                                                </button>
                                                            </TooltipTrigger>
                                                            <TooltipContent><p>Copy</p></TooltipContent>
                                                        </Tooltip>

                                                    </TooltipProvider>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </motion.div>
                            ))}
                            {/* Loading State */}
                            {loading && (
                                <motion.div
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    className="flex gap-4"
                                >
                                    <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-muted">
                                        <Sparkles className="w-4 h-4 text-foreground animate-pulse" />
                                    </div>
                                    <div className="flex-1">
                                        <div className="inline-block px-4 py-3 bg-muted rounded-2xl rounded-tl-md">
                                            <div className="flex items-center gap-2">
                                                <div className="flex gap-1">
                                                    <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                                    <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                                    <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                                </div>
                                                <span className="text-sm text-muted-foreground">Thinking...</span>
                                            </div>
                                        </div>
                                    </div>
                                </motion.div>
                            )}
                        </div>
                    </AnimatePresence>
                </div>
            </div>

            {/* Input Area - Absolute Bottom */}
            <div className="absolute bottom-0 left-0 right-0 border-t border-border bg-background z-20">
                <div className="w-full max-w-3xl xl:max-w-4xl 2xl:max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
                    <form onSubmit={handleSend} className="relative">
                        <div className="relative flex items-end bg-muted/50 rounded-2xl border border-input focus-within:ring-1 focus-within:ring-ring transition-all duration-200 hover:border-ring/50">
                            <textarea
                                ref={textareaRef}
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder={
                                    chatbotType === 'SOP' ? "Ask about SOPs..." :
                                        chatbotType === 'INSW' ? "Ask about HS Codes..." :
                                            "Message EXIM Assistant..."
                                }
                                disabled={loading || !sessionId}
                                rows={1}
                                className="flex-1 px-4 py-3 bg-transparent resize-none outline-none text-foreground placeholder:text-muted-foreground disabled:opacity-50 max-h-[200px] cursor-text min-h-[44px]"
                            />
                            <div className="flex items-center gap-1 px-2 pb-2">
                                <TooltipProvider delayDuration={300}>
                                    {loading ? (
                                        <Tooltip>
                                            <TooltipTrigger asChild>
                                                <Button
                                                    type="button"
                                                    variant="secondary"
                                                    size="icon"
                                                    className="cursor-pointer transition-all duration-200 hover:bg-destructive/10 hover:text-destructive h-8 w-8"
                                                >
                                                    <StopCircle className="w-5 h-5" />
                                                </Button>
                                            </TooltipTrigger>
                                            <TooltipContent>
                                                <p>Stop generating</p>
                                            </TooltipContent>
                                        </Tooltip>
                                    ) : (
                                        <Tooltip>
                                            <TooltipTrigger asChild>
                                                <Button
                                                    type="submit"
                                                    size="icon"
                                                    disabled={!input.trim() || !sessionId}
                                                    className="cursor-pointer transition-all duration-200 hover:shadow-md disabled:cursor-not-allowed h-8 w-8"
                                                >
                                                    <ArrowUp className="w-5 h-5" />
                                                </Button>
                                            </TooltipTrigger>
                                            <TooltipContent>
                                                <p>Send message</p>
                                            </TooltipContent>
                                        </Tooltip>
                                    )}
                                </TooltipProvider>
                            </div>
                        </div>
                    </form>
                    <p className="mt-2 text-center text-xs text-muted-foreground">
                        {chatbotType} Assistant may produce inaccurate information. Verify important details.
                    </p>
                </div>
            </div>
        </div>
    );

}

